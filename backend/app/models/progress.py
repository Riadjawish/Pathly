from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.learning import LearningLevel
    from app.models.subject import Subject
    from app.models.user import User


class ProgressEventType(str, Enum):
    MATERIAL_PROCESSED = "material_processed"
    LEVEL_STARTED = "level_started"
    LEVEL_COMPLETED = "level_completed"
    QUIZ_COMPLETED = "quiz_completed"
    PATH_GENERATED = "path_generated"
    STREAK_UPDATED = "streak_updated"


class SubjectProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subject_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "subject_id", name="uq_subject_progress_user_subject"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
        CheckConstraint("completed_levels >= 0", name="completed_levels_nonnegative"),
        CheckConstraint("total_levels >= 0", name="total_levels_nonnegative"),
        CheckConstraint("quizzes_completed >= 0", name="quizzes_completed_nonnegative"),
        CheckConstraint(
            "average_quiz_score >= 0 AND average_quiz_score <= 100",
            name="average_quiz_score_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_levels: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_levels: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quizzes_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_quiz_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    last_studied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="subject_progress")
    subject: Mapped[Subject] = relationship(back_populates="user_progress")


class ProgressEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "progress_events"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), index=True
    )
    level_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_levels.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[ProgressEventType] = mapped_column(
        SAEnum(
            ProgressEventType,
            name="progress_event_type",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        index=True,
        nullable=False,
    )
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="progress_events")
    subject: Mapped[Subject | None] = relationship(back_populates="progress_events")
    level: Mapped[LearningLevel | None] = relationship(back_populates="progress_events")
