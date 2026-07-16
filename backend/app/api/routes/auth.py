import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import or_, select, update

from app.api.deps import DB, CurrentUser
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_refresh_token,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.models import EmailVerificationToken, PasswordResetToken, RefreshToken, User
from app.schemas import (
    EmailVerificationConfirm,
    GoogleLoginRequest,
    LoginRequest,
    Message,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.services import get_outbox, send_email

router = APIRouter(prefix="/auth", tags=["auth"])

PASSWORD_RESET_TTL = timedelta(minutes=30)
EMAIL_VERIFICATION_TTL = timedelta(hours=24)


def normalized_email(value: str) -> str:
    return value.strip().lower()


async def create_session(db: DB, user: User, request: Request) -> TokenPair:
    raw_refresh = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
            created_at=datetime.now(UTC),
            user_agent=request.headers.get("user-agent", "")[:500] or None,
            ip_address=request.client.host[:64] if request.client else None,
        )
    )
    await db.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=raw_refresh)


async def send_verification_email(db: DB, user: User) -> None:
    raw_token = generate_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + EMAIL_VERIFICATION_TTL,
        )
    )
    await db.flush()
    link = f"{settings.frontend_base_url}/verify-email?token={raw_token}"
    send_email(
        user.email,
        "Verify your Pathly email",
        f"Confirm your email address to finish setting up Pathly:\n{link}",
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, db: DB) -> TokenPair:
    email = normalized_email(payload.email)
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    encoded = await asyncio.to_thread(hash_password, payload.password)
    user = User(
        email=email,
        password_hash=encoded,
        full_name=payload.full_name,
        email_verified=False,
    )
    db.add(user)
    await db.flush()
    await send_verification_email(db, user)
    return await create_session(db, user, request)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, request: Request, db: DB) -> TokenPair:
    user = await db.scalar(select(User).where(User.email == normalized_email(payload.email)))
    valid = bool(
        user
        and user.password_hash
        and await asyncio.to_thread(verify_password, payload.password, user.password_hash)
    )
    if not valid or user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await create_session(db, user, request)


def verify_google_token(raw_token: str) -> dict[str, object]:
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    try:
        claims = google_id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Google token is invalid or expired") from exc
    if not claims.get("email") or not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Google token is missing identity claims")
    if claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google email is not verified")
    return claims


@router.post("/google", response_model=TokenPair)
async def google_login(payload: GoogleLoginRequest, request: Request, db: DB) -> TokenPair:
    claims = await asyncio.to_thread(verify_google_token, payload.id_token)
    email = normalized_email(str(claims["email"]))
    google_sub = str(claims["sub"])
    user = await db.scalar(
        select(User).where(or_(User.google_sub == google_sub, User.email == email))
    )
    if user is None:
        user = User(
            email=email,
            google_sub=google_sub,
            full_name=str(claims.get("name") or email.split("@", 1)[0])[:120],
            avatar_url=str(claims["picture"]) if claims.get("picture") else None,
            email_verified=True,
        )
        db.add(user)
        await db.flush()
    else:
        if user.google_sub and user.google_sub != google_sub:
            raise HTTPException(
                status_code=409, detail="This email is linked to another Google account"
            )
        user.google_sub = google_sub
        user.email_verified = True
        if not user.avatar_url and claims.get("picture"):
            user.avatar_url = str(claims["picture"])
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return await create_session(db, user, request)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, request: Request, db: DB) -> TokenPair:
    token = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(payload.refresh_token),
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    if token is None:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired")
    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    token.revoked_at = datetime.now(UTC)
    await db.flush()
    return await create_session(db, user, request)


@router.post("/logout", response_model=Message)
async def logout(payload: RefreshRequest, db: DB) -> Message:
    token = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(payload.refresh_token),
            RefreshToken.revoked_at.is_(None),
        )
    )
    if token:
        token.revoked_at = datetime.now(UTC)
        await db.commit()
    return Message(message="Signed out")


GENERIC_RESET_MESSAGE = Message(
    message="If an account exists for that email, we've sent password reset instructions."
)


@router.post("/password-reset/request", response_model=Message)
async def request_password_reset(payload: PasswordResetRequest, db: DB) -> Message:
    email = normalized_email(payload.email)
    user = await db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is not None:
        raw_token = generate_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=datetime.now(UTC) + PASSWORD_RESET_TTL,
            )
        )
        await db.commit()
        link = f"{settings.frontend_base_url}/login/reset?token={raw_token}"
        send_email(
            user.email,
            "Reset your Pathly password",
            f"Use this link within 30 minutes to reset your password:\n{link}",
        )
    return GENERIC_RESET_MESSAGE


@router.post("/password-reset/confirm", response_model=Message)
async def confirm_password_reset(payload: PasswordResetConfirm, db: DB) -> Message:
    reset_token = await db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(payload.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(UTC),
        )
    )
    if reset_token is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")
    user = await db.get(User, reset_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")
    user.password_hash = await asyncio.to_thread(hash_password, payload.new_password)
    reset_token.used_at = datetime.now(UTC)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()
    return Message(message="Your password has been reset. Sign in with your new password.")


@router.post("/verify-email/request", response_model=Message)
async def request_email_verification(current_user: CurrentUser, db: DB) -> Message:
    if current_user.email_verified:
        return Message(message="Your email is already verified")
    await send_verification_email(db, current_user)
    await db.commit()
    return Message(message="Verification email sent")


@router.post("/verify-email/confirm", response_model=Message)
async def confirm_email_verification(payload: EmailVerificationConfirm, db: DB) -> Message:
    verification_token = await db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(payload.token),
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > datetime.now(UTC),
        )
    )
    if verification_token is None:
        raise HTTPException(
            status_code=400, detail="This verification link is invalid or has expired"
        )
    user = await db.get(User, verification_token.user_id)
    if user is None:
        raise HTTPException(
            status_code=400, detail="This verification link is invalid or has expired"
        )
    user.email_verified = True
    verification_token.used_at = datetime.now(UTC)
    await db.commit()
    return Message(message="Your email is verified")


@router.get("/dev-outbox", response_model=list[dict[str, str]])
async def dev_outbox(email: str) -> list[dict[str, str]]:
    if settings.environment == "production":
        raise HTTPException(status_code=404)
    return get_outbox(email)
