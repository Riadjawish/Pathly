from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.api.routes.learning import service_http_error
from app.api.routes.materials import gemini, vectors
from app.api.routes.subjects import owned_subject
from app.core.config import settings
from app.models import ChatConversation, ChatMessage, ChatRole
from app.schemas import ChatMessageRead, ChatReply, ChatRequest
from app.services import RAGService, ServiceError

router = APIRouter(prefix="/subjects/{subject_id}/chat", tags=["chat"])
rag = RAGService(gemini, vectors)


async def conversation_for(db: DB, user_id: UUID, subject_id: UUID) -> ChatConversation | None:
    return await db.scalar(
        select(ChatConversation)
        .options(selectinload(ChatConversation.messages))
        .where(
            ChatConversation.user_id == user_id,
            ChatConversation.subject_id == subject_id,
        )
    )


@router.get("", response_model=list[ChatMessageRead])
async def chat_history(
    subject_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> list[ChatMessage]:
    await owned_subject(db, current_user.id, subject_id)
    conversation = await conversation_for(db, current_user.id, subject_id)
    if conversation is None:
        return []
    return [message for message in conversation.messages if message.role != ChatRole.SYSTEM]


@router.post("", response_model=ChatReply)
async def send_message(
    subject_id: UUID,
    payload: ChatRequest,
    current_user: CurrentUser,
    db: DB,
) -> ChatReply:
    await owned_subject(db, current_user.id, subject_id)
    conversation = await conversation_for(db, current_user.id, subject_id)
    if conversation is None:
        conversation = ChatConversation(user_id=current_user.id, subject_id=subject_id)
        db.add(conversation)
        await db.flush()
    history = [
        {"role": message.role.value, "content": message.content}
        for message in conversation.messages[-10:]
        if message.role in {ChatRole.USER, ChatRole.ASSISTANT}
    ]
    user_message = ChatMessage(
        conversation_id=conversation.id,
        role=ChatRole.USER,
        content=payload.message.strip(),
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)
    try:
        answer = await rag.answer(
            subject_id=str(subject_id),
            question=payload.message,
            history=history,
        )
    except ServiceError as exc:
        raise service_http_error(exc) from exc
    assistant_message = ChatMessage(
        conversation_id=conversation.id,
        role=ChatRole.ASSISTANT,
        content=answer["answer"],
        sources=answer.get("sources", []),
        generated_by_model=settings.gemini_generation_model,
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)
    return ChatReply(
        user_message=ChatMessageRead.model_validate(user_message),
        assistant_message=ChatMessageRead.model_validate(assistant_message),
    )
