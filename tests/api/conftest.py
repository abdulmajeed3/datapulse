"""Database and HTTP client fixtures for API/integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://datapulse:datapulse@localhost:5432/datapulse_test"

_test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
_test_session_factory = async_sessionmaker(
    bind=_test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> AsyncGenerator[None, None]:
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ─── Auth helpers ─────────────────────────────────────────────────────


async def _create_user_and_login(
    client: AsyncClient,
    email: str = "test@example.com",
    username: str = "testuser",
    password: str = "TestPassword1",
) -> tuple[str, str]:
    """Register a user and return (access_token, refresh_token)."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    data = resp.json()
    return data["access_token"], data["refresh_token"]


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    access_token, _ = await _create_user_and_login(client)
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def auth_headers_b(client: AsyncClient) -> dict[str, str]:
    """Second user (User B) for authorization isolation tests."""
    access_token, _ = await _create_user_and_login(
        client,
        email="userb@example.com",
        username="userb",
        password="UserBPassword1",
    )
    return {"Authorization": f"Bearer {access_token}"}
