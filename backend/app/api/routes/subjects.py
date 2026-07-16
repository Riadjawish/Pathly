from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models import Subject
from app.schemas import SubjectCreate, SubjectRead, SubjectUpdate

router = APIRouter(prefix="/subjects", tags=["subjects"])


async def owned_subject(db: DB, user_id: UUID, subject_id: UUID) -> Subject:
    subject = await db.scalar(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == user_id,
            Subject.is_archived.is_(False),
        )
    )
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@router.get("", response_model=list[SubjectRead])
async def list_subjects(current_user: CurrentUser, db: DB) -> list[Subject]:
    result = await db.scalars(
        select(Subject)
        .where(Subject.user_id == current_user.id, Subject.is_archived.is_(False))
        .order_by(Subject.created_at.asc())
    )
    return list(result)


@router.post("", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    current_user: CurrentUser,
    db: DB,
) -> Subject:
    subject = Subject(user_id=current_user.id, **payload.model_dump())
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


@router.get("/{subject_id}", response_model=SubjectRead)
async def get_subject(subject_id: UUID, current_user: CurrentUser, db: DB) -> Subject:
    return await owned_subject(db, current_user.id, subject_id)


@router.patch("/{subject_id}", response_model=SubjectRead)
async def update_subject(
    subject_id: UUID,
    payload: SubjectUpdate,
    current_user: CurrentUser,
    db: DB,
) -> Subject:
    subject = await owned_subject(db, current_user.id, subject_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(subject, field, value)
    await db.commit()
    await db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> Response:
    subject = await owned_subject(db, current_user.id, subject_id)
    await db.delete(subject)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
