"""Core exceptions that are not part of the domain language."""


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or is malformed."""

    def __init__(self, message: str = "Invalid authentication token") -> None:
        self.message = message
        super().__init__(message)
