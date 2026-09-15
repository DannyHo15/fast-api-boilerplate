"""Domain exceptions.

The domain/application layers raise these; the API layer translates them
into HTTP responses (see `app.api.errors`). Keeping the translation in the
presentation layer keeps the domain free of HTTP knowledge.
"""


class DomainError(Exception):
    """Base class for all domain errors."""

    #: Machine-readable code used in the API error envelope.
    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    """An entity was not found (or is not visible to the caller)."""

    code = "NOT_FOUND"


class ConflictError(DomainError):
    """The operation conflicts with the current state (e.g. duplicate email)."""

    code = "CONFLICT"


class InvalidCredentialsError(DomainError):
    """Authentication failed (wrong password, expired/invalid token...)."""

    code = "INVALID_CREDENTIALS"


class RateLimitedError(DomainError):
    """Too many requests within the rate-limit window."""

    code = "RATE_LIMITED"

    def __init__(
        self,
        message: str = "Too many requests, please slow down",
        retry_after: int = 1,
    ) -> None:
        self.retry_after = max(int(retry_after), 1)
        super().__init__(message)
