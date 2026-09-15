"""PyJWT implementation of `app.domain.ports.token_service.TokenService`."""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.exceptions import InvalidTokenError


class JwtTokenService:
    def __init__(self, secret_key: str, algorithm: str, expires_minutes: int) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expires_minutes = expires_minutes

    def create_access_token(self, subject: str, *, expires_delta: timedelta | None = None) -> str:
        now = datetime.now(UTC)
        expires = now + (
            expires_delta if expires_delta is not None else timedelta(minutes=self._expires_minutes)
        )
        payload = {
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidTokenError("Token subject is missing")
        return subject
