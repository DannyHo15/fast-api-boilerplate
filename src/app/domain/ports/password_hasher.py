"""Port for one-way password hashing."""

from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        """Return a one-way hash of `password`."""
        ...

    def verify(self, password: str, password_hash: str) -> bool:
        """Check `password` against a stored `password_hash`."""
        ...
