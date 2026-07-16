from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class FriendStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class FriendRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "friend_requests"
    __table_args__ = (
        UniqueConstraint("sender_id", "receiver_id", name="uq_friend_request_pair"),
        CheckConstraint("sender_id <> receiver_id", name="different_users"),
    )

    sender_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    receiver_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[FriendStatus] = mapped_column(
        SAEnum(
            FriendStatus,
            name="friend_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=FriendStatus.PENDING,
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sender: Mapped[User] = relationship(
        foreign_keys=[sender_id], back_populates="friend_requests_sent"
    )
    receiver: Mapped[User] = relationship(
        foreign_keys=[receiver_id], back_populates="friend_requests_received"
    )


class Friendship(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="uq_friendship_pair"),
        CheckConstraint("user_id <> friend_id", name="different_users"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    friend_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    friend: Mapped[User] = relationship(foreign_keys=[friend_id])
