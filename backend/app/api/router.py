from fastapi import APIRouter

from app.api.routes import (
    auth,
    chat,
    friends,
    health,
    learning,
    materials,
    progress,
    quizzes,
    study,
    subjects,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(friends.router)
api_router.include_router(subjects.router)
api_router.include_router(materials.router)
api_router.include_router(learning.router)
api_router.include_router(quizzes.router)
api_router.include_router(chat.router)
api_router.include_router(study.router)
api_router.include_router(progress.router)
