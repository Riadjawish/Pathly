from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.api.routes.materials import learning_engine
from app.api.routes.subjects import owned_subject
from app.models import (
    LearningLevel,
    LearningPath,
    LevelKind,
    LevelStatus,
    Material,
    PathStatus,
    ProcessingStatus,
    ProgressEvent,
    ProgressEventType,
    SubjectProgress,
)
from app.schemas import GeneratePathRequest, LearningPathRead
from app.services import AIConfigurationError, AIResponseError, ServiceError

router = APIRouter(prefix="/subjects/{subject_id}/learning-path", tags=["learning"])


async def latest_path(db: DB, subject_id: UUID) -> LearningPath | None:
    return await db.scalar(
        select(LearningPath)
        .options(selectinload(LearningPath.levels))
        .where(LearningPath.subject_id == subject_id)
        .order_by(LearningPath.version.desc())
        .limit(1)
    )


def service_http_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, AIConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AIResponseError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.get("", response_model=LearningPathRead)
async def get_learning_path(
    subject_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> LearningPath:
    await owned_subject(db, current_user.id, subject_id)
    path = await latest_path(db, subject_id)
    if path is None:
        raise HTTPException(status_code=404, detail="No learning path has been generated yet")
    return path


@router.post("/generate", response_model=LearningPathRead)
async def generate_learning_path(
    subject_id: UUID,
    payload: GeneratePathRequest,
    current_user: CurrentUser,
    db: DB,
) -> LearningPath:
    subject = await owned_subject(db, current_user.id, subject_id)
    ready_count = await db.scalar(
        select(func.count(Material.id)).where(
            Material.subject_id == subject_id,
            Material.status == ProcessingStatus.READY,
        )
    )
    if not ready_count:
        raise HTTPException(
            status_code=409,
            detail="Process at least one uploaded material before generating a learning path",
        )
    version = (
        await db.scalar(
            select(func.max(LearningPath.version)).where(LearningPath.subject_id == subject_id)
        )
        or 0
    ) + 1
    path = LearningPath(
        subject_id=subject_id,
        title=f"{subject.name} mastery path",
        status=PathStatus.GENERATING,
        version=version,
    )
    db.add(path)
    await db.commit()
    await db.refresh(path)
    goal_parts = [part for part in [current_user.study_goal, *payload.instructions] if part]
    try:
        generated = await learning_engine.generate_learning_path(
            subject_id=str(subject_id),
            subject_name=subject.name,
            learner_goal="\n".join(goal_parts)[:3000] or None,
        )
        type_map = {
            "lesson": LevelKind.LESSON,
            "checkpoint": LevelKind.CHECKPOINT,
            "boss": LevelKind.BOSS,
        }
        levels = []
        for index, item in enumerate(generated["levels"]):
            levels.append(
                LearningLevel(
                    learning_path_id=path.id,
                    order_index=index,
                    chapter=item["chapter"],
                    title=item["title"],
                    description=item["description"],
                    kind=type_map.get(item["type"], LevelKind.LESSON),
                    status=LevelStatus.CURRENT if index == 0 else LevelStatus.LOCKED,
                    estimated_minutes=item["estimated_minutes"],
                    content={
                        "objectives": item.get("objectives", []),
                        "blocks": item.get("blocks", []),
                    },
                    source_refs=[{"id": source} for source in item.get("source_ids", [])],
                )
            )
        db.add_all(levels)
        path.title = generated["title"]
        path.summary = generated["summary"]
        path.status = PathStatus.READY
        path.generated_by_model = learning_engine.ai.generation_model
        subject.topics_count = len(levels)
        subject.progress = 0
        progress = await db.scalar(
            select(SubjectProgress).where(
                SubjectProgress.user_id == current_user.id,
                SubjectProgress.subject_id == subject_id,
            )
        )
        if progress is None:
            progress = SubjectProgress(user_id=current_user.id, subject_id=subject_id)
            db.add(progress)
        progress.total_levels = len(levels)
        progress.completed_levels = 0
        progress.progress = 0
        db.add(
            ProgressEvent(
                user_id=current_user.id,
                subject_id=subject_id,
                event_type=ProgressEventType.PATH_GENERATED,
                event_data={"path_id": str(path.id), "levels": len(levels)},
            )
        )
        await db.commit()
    except ServiceError as exc:
        await db.rollback()
        try:
            failed = await db.get(LearningPath, path.id)
            if failed:
                failed.status = PathStatus.FAILED
                failed.error_message = str(exc)[:2000]
                await db.commit()
        except Exception:
            await db.rollback()
        raise service_http_error(exc) from exc
    result = await latest_path(db, subject_id)
    assert result is not None
    return result


@router.post("/levels/{level_id}/complete", response_model=LearningPathRead)
async def complete_level(
    subject_id: UUID,
    level_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> LearningPath:
    subject = await owned_subject(db, current_user.id, subject_id)
    level = await db.scalar(
        select(LearningLevel)
        .join(LearningPath, LearningPath.id == LearningLevel.learning_path_id)
        .where(LearningLevel.id == level_id, LearningPath.subject_id == subject_id)
    )
    if level is None:
        raise HTTPException(status_code=404, detail="Learning level not found")
    if level.status == LevelStatus.LOCKED:
        raise HTTPException(status_code=409, detail="Complete the current level first")
    if level.status != LevelStatus.COMPLETE:
        level.status = LevelStatus.COMPLETE
        level.progress_percent = 100
        next_level = await db.scalar(
            select(LearningLevel).where(
                LearningLevel.learning_path_id == level.learning_path_id,
                LearningLevel.order_index == level.order_index + 1,
            )
        )
        if next_level and next_level.status == LevelStatus.LOCKED:
            next_level.status = LevelStatus.CURRENT
        today = date.today()
        if current_user.last_study_date != today:
            current_user.streak_days = (
                current_user.streak_days + 1
                if current_user.last_study_date == today - timedelta(days=1)
                else 1
            )
            current_user.last_study_date = today
        levels = list(
            await db.scalars(
                select(LearningLevel).where(
                    LearningLevel.learning_path_id == level.learning_path_id
                )
            )
        )
        completed = sum(item.status == LevelStatus.COMPLETE for item in levels)
        total = len(levels)
        percentage = round(completed / total * 100) if total else 0
        subject.progress = percentage
        progress = await db.scalar(
            select(SubjectProgress).where(
                SubjectProgress.user_id == current_user.id,
                SubjectProgress.subject_id == subject_id,
            )
        )
        if progress is None:
            progress = SubjectProgress(user_id=current_user.id, subject_id=subject_id)
            db.add(progress)
        progress.progress = percentage
        progress.completed_levels = completed
        progress.total_levels = total
        progress.last_studied_at = datetime.now(UTC)
        db.add(
            ProgressEvent(
                user_id=current_user.id,
                subject_id=subject_id,
                level_id=level.id,
                event_type=ProgressEventType.LEVEL_COMPLETED,
                event_data={"title": level.title, "progress": percentage},
            )
        )
        await db.commit()
    path = await db.scalar(
        select(LearningPath)
        .options(selectinload(LearningPath.levels))
        .where(LearningPath.id == level.learning_path_id)
    )
    assert path is not None
    return path
