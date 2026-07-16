from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.chat import ChatConversation
    from app.models.learning import LearningPath
    from app.models.material import Material
    from app.models.progress import ProgressEvent, SubjectProgress
    from app.models.quiz import Quiz
    from app.models.user import User


class Subject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
        CheckConstraint("topics_count >= 0", name="topics_count_nonnegative"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    short_name: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    icon: Mapped[str] = mapped_column(String(32), default="📚", nullable=False)
    tone: Mapped[str] = mapped_column(String(32), default="purple", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topics_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="subjects")
    materials: Mapped[list[Material]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", passive_deletes=True
    )
    learning_paths: Mapped[list[LearningPath]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", passive_deletes=True
    )
    quizzes: Mapped[list[Quiz]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", passive_deletes=True
    )
    conversations: Mapped[list[ChatConversation]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", passive_deletes=True
    )
    user_progress: Mapped[list[SubjectProgress]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", passive_deletes=True
    )
    progress_events: Mapped[list[ProgressEvent]] = relationship(
        back_populates="subject", passive_deletes=True
    )
