"""SQLAlchemy model registry.

Importing this module registers every table on ``Base.metadata`` for Alembic and tests.
"""

from app.models.chat import ChatConversation, ChatMessage, ChatRole
from app.models.learning import LearningLevel, LearningPath, LevelKind, LevelStatus, PathStatus
from app.models.material import (
    DocumentChunk,
    Material,
    MaterialCategory,
    MaterialKind,
    ProcessingStatus,
)
from app.models.progress import ProgressEvent, ProgressEventType, SubjectProgress
from app.models.quiz import (
    QuestionType,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    QuizStatus,
    QuizType,
)
from app.models.social import FriendRequest, Friendship, FriendStatus
from app.models.subject import Subject
from app.models.user import EmailVerificationToken, PasswordResetToken, RefreshToken, User

__all__ = [
    "ChatConversation",
    "ChatMessage",
    "ChatRole",
    "DocumentChunk",
    "EmailVerificationToken",
    "FriendRequest",
    "FriendStatus",
    "Friendship",
    "LearningLevel",
    "LearningPath",
    "LevelKind",
    "LevelStatus",
    "Material",
    "MaterialCategory",
    "MaterialKind",
    "PasswordResetToken",
    "PathStatus",
    "ProcessingStatus",
    "ProgressEvent",
    "ProgressEventType",
    "QuestionType",
    "Quiz",
    "QuizAttempt",
    "QuizQuestion",
    "QuizStatus",
    "QuizType",
    "RefreshToken",
    "Subject",
    "SubjectProgress",
    "User",
]
