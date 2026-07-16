from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.api.routes.learning import latest_path, service_http_error
from app.api.routes.materials import learning_engine
from app.api.routes.subjects import owned_subject
from app.models import Quiz, QuizAttempt
from app.schemas import (
    StudyRecommendations,
    StudySummary,
    SummaryRequest,
)
from app.services import ServiceError

router = APIRouter(prefix="/subjects/{subject_id}/study", tags=["study tools"])


@router.post("/summary", response_model=StudySummary)
async def generate_summary(
    subject_id: UUID,
    payload: SummaryRequest,
    current_user: CurrentUser,
    db: DB,
) -> StudySummary:
    subject = await owned_subject(db, current_user.id, subject_id)
    try:
        result = await learning_engine.generate_summary(
            subject_id=str(subject_id),
            subject_name=subject.name,
            topic=payload.topic.strip() if payload.topic else None,
        )
    except ServiceError as exc:
        raise service_http_error(exc) from exc
    return StudySummary.model_validate(result)


@router.get("/recommendations", response_model=StudyRecommendations)
async def recommend_next_topics(
    subject_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> StudyRecommendations:
    subject = await owned_subject(db, current_user.id, subject_id)
    path = await latest_path(db, subject_id)
    if path is None:
        raise HTTPException(status_code=409, detail="Generate a learning path first")
    attempts = list(
        await db.scalars(
            select(QuizAttempt)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .options(selectinload(QuizAttempt.quiz))
            .where(Quiz.subject_id == subject_id, QuizAttempt.user_id == current_user.id)
            .order_by(QuizAttempt.created_at.desc())
            .limit(10)
        )
    )
    levels = [
        {
            "title": level.title,
            "chapter": level.chapter,
            "status": level.status.value,
            "objectives": level.content.get("objectives", []),
        }
        for level in path.levels
    ]
    recent_results = [
        {"quiz": attempt.quiz.title, "score": attempt.score, "results": attempt.results}
        for attempt in attempts
    ]
    try:
        result = await learning_engine.recommend_next_topics(
            subject_name=subject.name,
            path_levels=levels,
            recent_results=recent_results,
        )
    except ServiceError as exc:
        raise service_http_error(exc) from exc
    return StudyRecommendations.model_validate(result)
