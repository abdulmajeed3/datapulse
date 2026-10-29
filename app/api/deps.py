"""FastAPI dependency functions for authentication and database access."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.security import get_token_subject
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user

_bearer = HTTPBearer(auto_error=False)


async def _get_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def get_authenticated_user(
    token: Annotated[str, Depends(_get_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        user_id = get_token_subject(token)
        return await get_current_user(db, user_id)
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[User, Depends(get_authenticated_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
