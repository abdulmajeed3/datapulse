"""Unit tests for security utilities."""

import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self) -> None:
        plain = "MySecurePassword123"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed)

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self) -> None:
        plain = "SamePassword1"
        h1 = hash_password(plain)
        h2 = hash_password(plain)
        # Argon2 uses a random salt each time
        assert h1 != h2
        assert verify_password(plain, h1)
        assert verify_password(plain, h2)

    def test_plaintext_not_stored(self) -> None:
        plain = "MyPassword123"
        hashed = hash_password(plain)
        assert plain not in hashed


class TestJWT:
    def test_create_and_decode(self) -> None:
        token = create_access_token("user-123")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_invalid_token_raises(self) -> None:
        with pytest.raises(UnauthorizedError):
            decode_access_token("not.a.valid.token")

    def test_tampered_token_raises(self) -> None:
        token = create_access_token("user-456")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(UnauthorizedError):
            decode_access_token(tampered)

    def test_extra_claims_preserved(self) -> None:
        token = create_access_token("u1", extra={"role": "admin"})
        payload = decode_access_token(token)
        assert payload["role"] == "admin"


class TestRefreshToken:
    def test_raw_and_hash_differ(self) -> None:
        raw, hashed = create_refresh_token()
        assert raw != hashed

    def test_hash_is_deterministic(self) -> None:
        raw, hashed = create_refresh_token()
        assert hash_refresh_token(raw) == hashed

    def test_different_tokens_have_different_hashes(self) -> None:
        _, h1 = create_refresh_token()
        _, h2 = create_refresh_token()
        assert h1 != h2
