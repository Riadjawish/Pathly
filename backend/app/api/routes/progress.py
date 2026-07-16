from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models import Material, ProgressEvent, Quiz, QuizAttempt, Subject, SubjectProgress
from app.schemas import ProgressEventRead, ProgressSubject, ProgressSummary

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/summary", response_model=ProgressSummary)
async def progress_summary(current_user: CurrentUser, db: DB) -> ProgressSummary:
    subjects = list(
        await db.scalars(
            select(Subject)
            .where(Subject.user_id == current_user.id, Subject.is_archived.is_(False))
            .order_by(Subject.created_at.asc())
        )
    )
    subject_ids = [subject.id for subject in subjects]
    progress_rows = (
        list(
            await db.scalars(
                select(SubjectProgress).where(
                    SubjectProgress.user_id == current_user.id,
                    SubjectProgress.subject_id.in_(subject_ids),
                )
            )
        )
        if subject_ids
        else []
    )
    progress_by_subject = {item.subject_id: item for item in progress_rows}
    materials_count = (
        await db.scalar(
            select(func.count(Material.id))
            .join(Subject, Subject.id == Material.subject_id)
            .where(Subject.user_id == current_user.id)
        )
        or 0
    )
    quiz_stats = (
        await db.execute(
            select(func.count(QuizAttempt.id), func.avg(QuizAttempt.score))
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .join(Subject, Subject.id == Quiz.subject_id)
            .where(QuizAttempt.user_id == current_user.id, Subject.user_id == current_user.id)
        )
    ).one()
    subject_summaries = []
    for subject in subjects:
        progress = progress_by_subject.get(subject.id)
        subject_summaries.append(
            ProgressSubject(
                subject_id=subject.id,
                name=subject.name,
                icon=subject.icon,
                progress=progress.progress if progress else subject.progress,
                completed_levels=progress.completed_levels if progress else 0,
                total_levels=progress.total_levels if progress else subject.topics_count,
            )
        )
    return ProgressSummary(
        streak_days=current_user.streak_days,
        subjects_count=len(subjects),
        materials_count=materials_count,
        quizzes_completed=int(quiz_stats[0] or 0),
        average_quiz_score=round(float(quiz_stats[1] or 0), 1),
        completed_levels=sum(item.completed_levels for item in subject_summaries),
        subjects=subject_summaries,
    )


@router.get("/history", response_model=list[ProgressEventRead])
async def progress_history(
    current_user: CurrentUser,
    db: DB,
    limit: int = 50,
) -> list[ProgressEventRead]:
    count = max(1, min(limit, 200))
    events = await db.scalars(
        select(ProgressEvent)
        .where(ProgressEvent.user_id == current_user.id)
        .order_by(ProgressEvent.created_at.desc())
        .limit(count)
    )
    return [
        ProgressEventRead(
            id=event.id,
            event_type=event.event_type.value,
            payload=event.event_data,
            created_at=event.created_at,
        )
        for event in events
    ]
