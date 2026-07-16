from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.schemas import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
async def update_me(payload: UserUpdate, current_user: CurrentUser, db: DB) -> UserRead:
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return UserRead.model_validate(current_user)
