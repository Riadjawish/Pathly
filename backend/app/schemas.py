from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=20)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=8, max_length=128)


class EmailVerificationConfirm(BaseModel):
    token: str = Field(min_length=20)


class UserRead(ORMModel):
    id: UUID
    email: EmailStr
    full_name: str
    avatar_url: str | None
    university: str | None
    course: str | None
    study_goal: str | None
    streak_days: int
    email_verified: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=2048)
    university: str | None = Field(default=None, max_length=180)
    course: str | None = Field(default=None, max_length=180)
    study_goal: str | None = Field(default=None, max_length=1000)


class SubjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    short_name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=500)
    icon: str = Field(default="✨", min_length=1, max_length=24)
    tone: str = Field(default="purple", min_length=2, max_length=32)

    @field_validator("name", "short_name", "description", "icon", "tone")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    short_name: str | None = Field(default=None, min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, min_length=1, max_length=24)
    tone: str | None = Field(default=None, min_length=2, max_length=32)


class SubjectRead(SubjectBase, ORMModel):
    id: UUID
    progress: int
    topics_count: int
    created_at: datetime
    updated_at: datetime


MaterialKind = Literal["course", "notes", "exams", "practice"]
MaterialStatus = Literal["uploaded", "processing", "ready", "failed"]


class MaterialRead(ORMModel):
    id: UUID
    subject_id: UUID
    kind: MaterialKind
    original_name: str
    content_type: str
    size_bytes: int
    status: MaterialStatus
    error_message: str | None
    extracted_chars: int
    created_at: datetime


class FriendInviteRequest(BaseModel):
    email: EmailStr


class FriendUser(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    avatar_url: str | None
    streak_days: int


class FriendRequestRead(ORMModel):
    id: UUID
    status: str
    created_at: datetime
    sender: FriendUser
    receiver: FriendUser


class FriendRead(FriendUser):
    friends_since: datetime


LevelStatus = Literal["locked", "current", "complete"]
LevelKind = Literal["lesson", "summary", "practice", "checkpoint", "boss", "final_review"]
PathStatus = Literal["generating", "ready", "failed"]


class LearningLevelRead(ORMModel):
    id: UUID
    order_index: int
    chapter: str
    title: str
    description: str
    status: LevelStatus
    kind: LevelKind
    estimated_minutes: int
    content: dict[str, Any]


class LearningPathRead(ORMModel):
    id: UUID
    subject_id: UUID
    title: str
    summary: str
    status: PathStatus
    levels: list[LearningLevelRead]
    created_at: datetime
    updated_at: datetime


class GeneratePathRequest(BaseModel):
    instructions: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("instructions")
    @classmethod
    def clean_instructions(cls, values: list[str]) -> list[str]:
        return [value.strip()[:1000] for value in values if value.strip()]


class GenerateQuizRequest(BaseModel):
    level_id: UUID | None = None
    count: int = Field(default=8, ge=3, le=25)
    difficulty: Literal["easy", "medium", "hard", "adaptive"] = "adaptive"


class QuizQuestionRead(ORMModel):
    id: UUID
    order_index: int
    prompt: str
    question_type: str
    options: list[str]
    explanation: str | None = None


class QuizRead(ORMModel):
    id: UUID
    subject_id: UUID
    level_id: UUID | None
    title: str
    difficulty: str
    questions: list[QuizQuestionRead]
    created_at: datetime


class QuizSubmitRequest(BaseModel):
    answers: dict[UUID, str]


class QuizAnswerResult(BaseModel):
    question_id: UUID
    correct: bool
    correct_answer: str
    explanation: str


class QuizAttemptRead(ORMModel):
    id: UUID
    quiz_id: UUID
    score: int
    correct_count: int
    total_count: int
    results: list[QuizAnswerResult]
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class ChatMessageRead(ORMModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[dict[str, Any]]
    created_at: datetime


class ChatReply(BaseModel):
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead


class SummaryRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=300)


class StudySummary(BaseModel):
    title: str
    overview: str
    key_points: list[str]
    must_remember: list[str]
    common_mistakes: list[str]
    source_ids: list[str]


class StudyRecommendation(BaseModel):
    topic: str
    reason: str
    priority: int
    suggested_activity: Literal["lesson", "practice", "quiz"]


class StudyRecommendations(BaseModel):
    recommendations: list[StudyRecommendation]
    encouragement: str


class HintRead(BaseModel):
    question_id: UUID
    hint: str


class ProgressSubject(BaseModel):
    subject_id: UUID
    name: str
    icon: str
    progress: int
    completed_levels: int
    total_levels: int


class ProgressSummary(BaseModel):
    streak_days: int
    subjects_count: int
    materials_count: int
    quizzes_completed: int
    average_quiz_score: float
    completed_levels: int
    subjects: list[ProgressSubject]


class ProgressEventRead(ORMModel):
    id: UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
