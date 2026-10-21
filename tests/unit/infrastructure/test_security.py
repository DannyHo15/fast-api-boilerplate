"""Unit tests for the security adapters (bcrypt, JWT)."""

from datetime import timedelta

import pytest

from app.core.exceptions import InvalidTokenError
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from app.infrastructure.security.jwt_token_service import JwtTokenService


def test_bcrypt_roundtrip() -> None:
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("supersecret1")
    assert hashed != "supersecret1"
    assert hasher.verify("supersecret1", hashed) is True
    assert hasher.verify("wrongpassword", hashed) is False


def test_bcrypt_rejects_malformed_hash() -> None:
    hasher = BcryptPasswordHasher()
    assert hasher.verify("anything", "not-a-valid-hash") is False


TEST_SECRET = "test-secret-key-0123456789-01234567890123"
OTHER_SECRET = "other-secret-key-0123456789-01234567890123"


def _service() -> JwtTokenService:
    return JwtTokenService(secret_key=TEST_SECRET, algorithm="HS256", expires_minutes=60)


def test_jwt_roundtrip() -> None:
    service = _service()
    token = service.create_access_token("user-123")
    assert service.decode_access_token(token) == "user-123"


def test_jwt_expired_token_is_rejected() -> None:
    service = _service()
    token = service.create_access_token("user-123", expires_delta=timedelta(seconds=-10))
    with pytest.raises(InvalidTokenError):
        service.decode_access_token(token)


@pytest.mark.parametrize("token", ["garbage", "a.b.c", ""])
def test_jwt_invalid_tokens_are_rejected(token: str) -> None:
    service = _service()
    with pytest.raises(InvalidTokenError):
        service.decode_access_token(token)


def test_jwt_wrong_secret_is_rejected() -> None:
    other = JwtTokenService(secret_key=OTHER_SECRET, algorithm="HS256", expires_minutes=60)
    token = _service().create_access_token("user-123")
    with pytest.raises(InvalidTokenError):
        other.decode_access_token(token)
