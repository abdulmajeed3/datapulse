"""API tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "username": "newuser", "password": "NewPass1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert "hashed_password" not in data
        assert "password" not in data

    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        payload = {"email": "dup@example.com", "username": "dupuser1", "password": "DupPass1"}
        await client.post("/api/v1/auth/register", json=payload)
        payload2 = {"email": "dup@example.com", "username": "dupuser2", "password": "DupPass1"}
        resp = await client.post("/api/v1/auth/register", json=payload2)
        assert resp.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "username": "weakuser", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "username": "user123", "password": "ValidPass1"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={"email": "login@example.com", "username": "loginuser", "password": "LoginPass1"},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "LoginPass1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpw@example.com",
                "username": "wrongpwuser",
                "password": "CorrectPw1",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@example.com", "password": "WrongPassword1"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "GhostPass1"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestRefreshAndLogout:
    async def test_refresh_success(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "username": "refreshuser",
                "password": "RefreshPw1",
            },
        )
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "refresh@example.com", "password": "RefreshPw1"},
        )
        refresh_token = login_resp.json()["refresh_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_logout_revokes_refresh_token(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={"email": "logout@example.com", "username": "logoutuser", "password": "LogoutPw1"},
        )
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "logout@example.com", "password": "LogoutPw1"},
        )
        refresh_token = login_resp.json()["refresh_token"]
        await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
        # Using the revoked token should fail
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    async def test_invalid_refresh_token_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "invalid-token-value"}
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestCurrentUser:
    async def test_get_me(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.get("/api/v1/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert "hashed_password" not in data

    async def test_get_me_unauthenticated(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401
