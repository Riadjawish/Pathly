from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.progress import ProgressEvent
    from app.models.quiz import Quiz
    from app.models.subject import Subject


class PathStatus(str, Enum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class LevelStatus(str, Enum):
    LOCKED = "locked"
    CURRENT = "current"
    COMPLETE = "complete"


class LevelKind(str, Enum):
    LESSON = "lesson"
    SUMMARY = "summary"
    PRACTICE = "practice"
    CHECKPOINT = "checkpoint"
    BOSS = "boss"
    FINAL_REVIEW = "final_review"


class LearningPath(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_paths"
    __table_args__ = (
        UniqueConstraint("subject_id", "version", name="uq_learning_path_subject_version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[PathStatus] = mapped_column(
        SAEnum(
            PathStatus,
            name="path_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=PathStatus.GENERATING,
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    generated_by_model: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    subject: Mapped[Subject] = relationship(back_populates="learning_paths")
    levels: Mapped[list[LearningLevel]] = relationship(
        back_populates="learning_path",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LearningLevel.order_index",
    )
    quizzes: Mapped[list[Quiz]] = relationship(back_populates="learning_path", passive_deletes=True)


class LearningLevel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_levels"
    __table_args__ = (
        UniqueConstraint("learning_path_id", "order_index", name="uq_learning_level_order"),
        CheckConstraint("order_index >= 0", name="order_nonnegative"),
        CheckConstraint("estimated_minutes >= 0", name="minutes_nonnegative"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="progress_range"),
    )

    learning_path_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_paths.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter: Mapped[str] = mapped_column(String(120), default="Core", nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kind: Mapped[LevelKind] = mapped_column(
        SAEnum(
            LevelKind,
            name="level_kind",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=LevelKind.LESSON,
        nullable=False,
    )
    status: Mapped[LevelStatus] = mapped_column(
        SAEnum(
            LevelStatus,
            name="level_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=LevelStatus.LOCKED,
        index=True,
        nullable=False,
    )
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    learning_path: Mapped[LearningPath] = relationship(back_populates="levels")
    quizzes: Mapped[list[Quiz]] = relationship(back_populates="level", passive_deletes=True)
    progress_events: Mapped[list[ProgressEvent]] = relationship(
        back_populates="level", passive_deletes=True
    )
