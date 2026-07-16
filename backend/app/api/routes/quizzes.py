from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.api.routes.learning import service_http_error
from app.api.routes.materials import learning_engine
from app.api.routes.subjects import owned_subject
from app.core.config import settings
from app.models import (
    LearningLevel,
    LearningPath,
    ProgressEvent,
    ProgressEventType,
    QuestionType,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    QuizStatus,
    QuizType,
    SubjectProgress,
)
from app.schemas import (
    GenerateQuizRequest,
    HintRead,
    QuizAnswerResult,
    QuizAttemptRead,
    QuizQuestionRead,
    QuizRead,
    QuizSubmitRequest,
)
from app.services import ServiceError

router = APIRouter(prefix="/subjects/{subject_id}/quizzes", tags=["quizzes"])


async def owned_quiz(db: DB, subject_id: UUID, quiz_id: UUID) -> Quiz:
    quiz = await db.scalar(
        select(Quiz)
        .options(selectinload(Quiz.questions))
        .where(Quiz.id == quiz_id, Quiz.subject_id == subject_id)
    )
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


def public_quiz(quiz: Quiz) -> QuizRead:
    return QuizRead(
        id=quiz.id,
        subject_id=quiz.subject_id,
        level_id=quiz.level_id,
        title=quiz.title,
        difficulty=quiz.difficulty,
        created_at=quiz.created_at,
        questions=[
            QuizQuestionRead(
                id=question.id,
                order_index=question.order_index,
                prompt=question.prompt,
                question_type=question.question_type.value,
                options=question.options,
                explanation=None,
            )
            for question in quiz.questions
        ],
    )


@router.post("/generate", response_model=QuizRead)
async def generate_quiz(
    subject_id: UUID,
    payload: GenerateQuizRequest,
    current_user: CurrentUser,
    db: DB,
) -> QuizRead:
    subject = await owned_subject(db, current_user.id, subject_id)
    level: LearningLevel | None = None
    if payload.level_id:
        level = await db.scalar(
            select(LearningLevel)
            .join(LearningPath, LearningPath.id == LearningLevel.learning_path_id)
            .where(
                LearningLevel.id == payload.level_id,
                LearningPath.subject_id == subject_id,
            )
        )
        if level is None:
            raise HTTPException(status_code=404, detail="Learning level not found")
    topic = level.title if level else subject.name
    quiz = Quiz(
        subject_id=subject_id,
        learning_path_id=level.learning_path_id if level else None,
        level_id=level.id if level else None,
        title=f"{topic} practice",
        difficulty=payload.difficulty,
        quiz_type=QuizType.CHECKPOINT if level else QuizType.PRACTICE,
        status=QuizStatus.GENERATING,
    )
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)
    try:
        generated = await learning_engine.generate_quiz(
            subject_id=str(subject_id),
            subject_name=subject.name,
            topic=topic,
            question_count=payload.count,
            difficulty="mixed" if payload.difficulty == "adaptive" else payload.difficulty,
        )
        quiz.title = generated["title"]
        quiz.status = QuizStatus.READY
        quiz.generated_by_model = settings.gemini_generation_model
        for index, item in enumerate(generated["questions"]):
            choices = item["choices"]
            db.add(
                QuizQuestion(
                    quiz_id=quiz.id,
                    order_index=index,
                    prompt=item["prompt"],
                    question_type=QuestionType.MULTIPLE_CHOICE,
                    options=choices,
                    correct_answer=choices[item["correct_index"]],
                    explanation=item["explanation"],
                    hint=item["hint"],
                    source_refs=[{"id": source} for source in item.get("source_ids", [])],
                )
            )
        await db.commit()
    except ServiceError as exc:
        await db.rollback()
        failed = await db.get(Quiz, quiz.id)
        if failed:
            failed.status = QuizStatus.FAILED
            failed.error_message = str(exc)[:2000]
            await db.commit()
        raise service_http_error(exc) from exc
    quiz = await owned_quiz(db, subject_id, quiz.id)
    return public_quiz(quiz)


@router.get("/{quiz_id}", response_model=QuizRead)
async def get_quiz(
    subject_id: UUID,
    quiz_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> QuizRead:
    await owned_subject(db, current_user.id, subject_id)
    quiz = await owned_quiz(db, subject_id, quiz_id)
    if quiz.status != QuizStatus.READY:
        raise HTTPException(status_code=409, detail=f"Quiz is {quiz.status.value}")
    return public_quiz(quiz)


@router.get("/{quiz_id}/questions/{question_id}/hint", response_model=HintRead)
async def get_question_hint(
    subject_id: UUID,
    quiz_id: UUID,
    question_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> HintRead:
    await owned_subject(db, current_user.id, subject_id)
    quiz = await owned_quiz(db, subject_id, quiz_id)
    question = next((item for item in quiz.questions if item.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="Quiz question not found")
    return HintRead(
        question_id=question.id,
        hint=question.hint or "Review the related learning level and eliminate unlikely choices.",
    )


def answer_matches(question: QuizQuestion, supplied: str | None) -> bool:
    if supplied is None:
        return False
    value = supplied.strip()
    if value.isdigit():
        index = int(value)
        if 0 <= index < len(question.options):
            value = question.options[index]
    return value.casefold() == question.correct_answer.strip().casefold()


@router.post("/{quiz_id}/submit", response_model=QuizAttemptRead)
async def submit_quiz(
    subject_id: UUID,
    quiz_id: UUID,
    payload: QuizSubmitRequest,
    current_user: CurrentUser,
    db: DB,
) -> QuizAttemptRead:
    await owned_subject(db, current_user.id, subject_id)
    quiz = await owned_quiz(db, subject_id, quiz_id)
    if quiz.status != QuizStatus.READY:
        raise HTTPException(status_code=409, detail="Quiz is not ready")
    if not quiz.questions:
        raise HTTPException(status_code=409, detail="Quiz has no questions")
    results: list[QuizAnswerResult] = []
    correct = 0
    for question in quiz.questions:
        supplied = payload.answers.get(question.id)
        is_correct = answer_matches(question, supplied)
        correct += int(is_correct)
        results.append(
            QuizAnswerResult(
                question_id=question.id,
                correct=is_correct,
                correct_answer=question.correct_answer,
                explanation=question.explanation or "",
            )
        )
    total = len(quiz.questions)
    score = round(correct / total * 100)
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=current_user.id,
        score=score,
        correct_count=correct,
        total_count=total,
        answers={str(key): value for key, value in payload.answers.items()},
        results=[result.model_dump(mode="json") for result in results],
    )
    db.add(attempt)
    await db.flush()
    today = date.today()
    if current_user.last_study_date != today:
        current_user.streak_days = (
            current_user.streak_days + 1
            if current_user.last_study_date == today - timedelta(days=1)
            else 1
        )
        current_user.last_study_date = today
    progress = await db.scalar(
        select(SubjectProgress).where(
            SubjectProgress.user_id == current_user.id,
            SubjectProgress.subject_id == subject_id,
        )
    )
    if progress is None:
        progress = SubjectProgress(user_id=current_user.id, subject_id=subject_id)
        db.add(progress)
    previous_count = progress.quizzes_completed
    progress.quizzes_completed = previous_count + 1
    progress.average_quiz_score = (
        progress.average_quiz_score * previous_count + score
    ) / progress.quizzes_completed
    progress.last_studied_at = datetime.now(UTC)
    db.add(
        ProgressEvent(
            user_id=current_user.id,
            subject_id=subject_id,
            level_id=quiz.level_id,
            event_type=ProgressEventType.QUIZ_COMPLETED,
            event_data={"quiz_id": str(quiz.id), "score": score},
        )
    )
    await db.commit()
    await db.refresh(attempt)
    return QuizAttemptRead.model_validate(attempt)
