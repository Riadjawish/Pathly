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
    from app.models.learning import LearningLevel, LearningPath
    from app.models.subject import Subject
    from app.models.user import User


class QuizStatus(str, Enum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class QuizType(str, Enum):
    PRACTICE = "practice"
    CHECKPOINT = "checkpoint"
    BOSS = "boss"
    CUSTOM = "custom"


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class Quiz(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quizzes"

    subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    learning_path_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_paths.id", ondelete="SET NULL"), index=True
    )
    level_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_levels.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(24), default="adaptive", nullable=False)
    quiz_type: Mapped[QuizType] = mapped_column(
        SAEnum(
            QuizType,
            name="quiz_type",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=QuizType.PRACTICE,
        nullable=False,
    )
    status: Mapped[QuizStatus] = mapped_column(
        SAEnum(
            QuizStatus,
            name="quiz_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=QuizStatus.GENERATING,
        index=True,
        nullable=False,
    )
    generated_by_model: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)

    subject: Mapped[Subject] = relationship(back_populates="quizzes")
    learning_path: Mapped[LearningPath | None] = relationship(back_populates="quizzes")
    level: Mapped[LearningLevel | None] = relationship(back_populates="quizzes")
    questions: Mapped[list[QuizQuestion]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QuizQuestion.order_index",
    )
    attempts: Mapped[list[QuizAttempt]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", passive_deletes=True
    )


class QuizQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "order_index", name="uq_quiz_question_order"),
        CheckConstraint("order_index >= 0", name="order_nonnegative"),
        CheckConstraint("points >= 1", name="points_positive"),
    )

    quiz_id: Mapped[UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        SAEnum(
            QuestionType,
            name="question_type",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=QuestionType.MULTIPLE_CHOICE,
        nullable=False,
    )
    options: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    hint: Mapped[str | None] = mapped_column(Text)
    points: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    quiz: Mapped[Quiz] = relationship(back_populates="questions")


class QuizAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
        CheckConstraint("correct_count >= 0", name="correct_count_nonnegative"),
        CheckConstraint("total_count >= 0", name="total_count_nonnegative"),
    )

    quiz_id: Mapped[UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    answers: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    quiz: Mapped[Quiz] = relationship(back_populates="attempts")
    user: Mapped[User] = relationship(back_populates="quiz_attempts")
