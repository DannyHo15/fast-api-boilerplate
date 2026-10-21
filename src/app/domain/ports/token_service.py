"""Port for issuing and validating access tokens."""

from datetime import timedelta
from typing import Protocol


class TokenService(Protocol):
    def create_access_token(self, subject: str, *, expires_delta: timedelta | None = None) -> str:
        """Create a signed token whose `sub` claim is `subject` (a user id)."""
        ...

    def decode_access_token(self, token: str) -> str:
        """Validate `token` and return the subject (user id) it encodes.

        Raises `app.core.exceptions.InvalidTokenError` on any failure.
        """
        ...
