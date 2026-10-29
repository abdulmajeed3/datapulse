from fastapi import APIRouter, HTTPException, status
from fastapi.security import HTTPBearer

from app.api.deps import DB
from app.core.exceptions import ConflictError, UnauthorizedError
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import (
    login_user,
    refresh_tokens,
    register_user,
    revoke_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])

_bearer = HTTPBearer(auto_error=False)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: DB) -> UserResponse:
    try:
        user = await register_user(db, data)
        return UserResponse.model_validate(user)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: DB) -> TokenResponse:
    try:
        return await login_user(db, data.email, data.password)
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: DB) -> TokenResponse:
    try:
        return await refresh_tokens(db, data.refresh_token)
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: RefreshRequest,
    db: DB,
) -> None:
    await revoke_refresh_token(db, data.refresh_token)
