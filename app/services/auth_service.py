"""Authentication service: registration, login, token management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenResponse


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    # Check email uniqueness
    existing_email = await db.scalar(select(User).where(User.email == data.email.lower()))
    if existing_email is not None:
        raise ConflictError("A user with this email already exists.")

    existing_username = await db.scalar(select(User).where(User.username == data.username.lower()))
    if existing_username is not None:
        raise ConflictError("A user with this username already exists.")

    user = User(
        email=data.email.lower(),
        username=data.username.lower(),
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password.")

    if not user.is_active:
        raise UnauthorizedError("Account is disabled.")

    return await _issue_tokens(db, user)


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    settings = get_settings()
    access_token = create_access_token(str(user.id))
    raw_refresh, hashed_refresh = create_refresh_token()

    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_record)
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def refresh_tokens(db: AsyncSession, raw_refresh_token: str) -> TokenResponse:
    token_hash = hash_refresh_token(raw_refresh_token)
    record = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if record is None or record.revoked or record.expires_at < datetime.now(UTC):
        raise UnauthorizedError("Refresh token is invalid or expired.")

    # Rotate: revoke old token
    record.revoked = True
    await db.flush()

    user = await db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User account not found or disabled.")

    return await _issue_tokens(db, user)


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    record = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if record is not None:
        record.revoked = True
        await db.flush()


async def get_current_user(db: AsyncSession, user_id_str: str) -> User:
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise UnauthorizedError("Invalid token subject.") from exc

    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found.")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled.")
    return user
