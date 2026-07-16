from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.models import FriendRequest, Friendship, FriendStatus, User
from app.schemas import FriendInviteRequest, FriendRead, FriendRequestRead, FriendUser

router = APIRouter(prefix="/friends", tags=["friends"])


def public_friend(user: User) -> FriendUser:
    return FriendUser(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        avatar_url=user.avatar_url,
        streak_days=user.streak_days,
    )


def request_read(item: FriendRequest) -> FriendRequestRead:
    return FriendRequestRead(
        id=item.id,
        status=item.status.value,
        created_at=item.created_at,
        sender=public_friend(item.sender),
        receiver=public_friend(item.receiver),
    )


@router.get("", response_model=list[FriendRead])
async def list_friends(current_user: CurrentUser, db: DB) -> list[FriendRead]:
    rows = (
        await db.execute(
            select(Friendship, User)
            .join(User, User.id == Friendship.friend_id)
            .where(Friendship.user_id == current_user.id)
            .order_by(Friendship.created_at.desc())
        )
    ).all()
    return [
        FriendRead(**public_friend(user).model_dump(), friends_since=friendship.created_at)
        for friendship, user in rows
    ]


@router.get("/requests", response_model=list[FriendRequestRead])
async def list_requests(current_user: CurrentUser, db: DB) -> list[FriendRequestRead]:
    items = await db.scalars(
        select(FriendRequest)
        .options(selectinload(FriendRequest.sender), selectinload(FriendRequest.receiver))
        .where(
            or_(
                FriendRequest.sender_id == current_user.id,
                FriendRequest.receiver_id == current_user.id,
            ),
            FriendRequest.status == FriendStatus.PENDING,
        )
        .order_by(FriendRequest.created_at.desc())
    )
    return [request_read(item) for item in items]


@router.post("/requests", response_model=FriendRequestRead, status_code=status.HTTP_201_CREATED)
async def invite_friend(
    payload: FriendInviteRequest,
    current_user: CurrentUser,
    db: DB,
) -> FriendRequestRead:
    target = await db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if target is None:
        raise HTTPException(status_code=404, detail="No Pathly user has that email")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot add yourself")
    friendship = await db.scalar(
        select(Friendship.id).where(
            Friendship.user_id == current_user.id,
            Friendship.friend_id == target.id,
        )
    )
    if friendship:
        raise HTTPException(status_code=409, detail="You are already friends")
    existing = await db.scalar(
        select(FriendRequest)
        .options(selectinload(FriendRequest.sender), selectinload(FriendRequest.receiver))
        .where(
            or_(
                and_(
                    FriendRequest.sender_id == current_user.id,
                    FriendRequest.receiver_id == target.id,
                ),
                and_(
                    FriendRequest.sender_id == target.id,
                    FriendRequest.receiver_id == current_user.id,
                ),
            )
        )
    )
    if existing and existing.status == FriendStatus.PENDING:
        raise HTTPException(status_code=409, detail="A friend request is already pending")
    if existing:
        existing.sender_id = current_user.id
        existing.receiver_id = target.id
        existing.status = FriendStatus.PENDING
        existing.responded_at = None
        item = existing
    else:
        item = FriendRequest(sender_id=current_user.id, receiver_id=target.id)
        db.add(item)
    await db.commit()
    item = await db.scalar(
        select(FriendRequest)
        .options(selectinload(FriendRequest.sender), selectinload(FriendRequest.receiver))
        .where(FriendRequest.id == item.id)
    )
    assert item is not None
    return request_read(item)


@router.post("/requests/{request_id}/accept", response_model=FriendRead)
async def accept_request(
    request_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> FriendRead:
    item = await db.scalar(
        select(FriendRequest)
        .options(selectinload(FriendRequest.sender))
        .where(
            FriendRequest.id == request_id,
            FriendRequest.receiver_id == current_user.id,
            FriendRequest.status == FriendStatus.PENDING,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Pending friend request not found")
    now = datetime.now(UTC)
    item.status = FriendStatus.ACCEPTED
    item.responded_at = now
    db.add_all(
        [
            Friendship(user_id=current_user.id, friend_id=item.sender_id, created_at=now),
            Friendship(user_id=item.sender_id, friend_id=current_user.id, created_at=now),
        ]
    )
    await db.commit()
    return FriendRead(**public_friend(item.sender).model_dump(), friends_since=now)


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def decline_or_cancel_request(
    request_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> Response:
    item = await db.scalar(
        select(FriendRequest).where(
            FriendRequest.id == request_id,
            or_(
                FriendRequest.sender_id == current_user.id,
                FriendRequest.receiver_id == current_user.id,
            ),
            FriendRequest.status == FriendStatus.PENDING,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Pending friend request not found")
    item.status = (
        FriendStatus.CANCELLED if item.sender_id == current_user.id else FriendStatus.DECLINED
    )
    item.responded_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(friend_id: UUID, current_user: CurrentUser, db: DB) -> Response:
    result = await db.execute(
        delete(Friendship).where(
            or_(
                and_(Friendship.user_id == current_user.id, Friendship.friend_id == friend_id),
                and_(Friendship.user_id == friend_id, Friendship.friend_id == current_user.id),
            )
        )
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Friend not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
