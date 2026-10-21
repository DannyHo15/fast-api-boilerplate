"""Exception handlers.

Central place where domain errors (and anything unexpected) become
consistent HTTP error envelopes:

    {"error": {"code": "NOT_FOUND", "message": "Task ... not found"}}
"""

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import DomainError, InvalidCredentialsError, RateLimitedError

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": jsonable_encoder(details) if details is not None else None,
            }
        },
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        """Translate domain errors to the appropriate HTTP status."""
        status_code = {
            "NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "CONFLICT": status.HTTP_409_CONFLICT,
            "INVALID_CREDENTIALS": status.HTTP_401_UNAUTHORIZED,
            "RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
        }.get(exc.code, status.HTTP_400_BAD_REQUEST)
        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after)
        if isinstance(exc, InvalidCredentialsError):
            headers["WWW-Authenticate"] = "Bearer"  # required on 401 (RFC 6750)
        return _error_response(status_code, exc.code, exc.message, headers=headers)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request error"
        # Keep protocol headers such as WWW-Authenticate (401) and Allow (405).
        return _error_response(exc.status_code, "HTTP_ERROR", message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422,  # status.HTTP_422_UNPROCESSABLE_ENTITY is deprecated in newer Starlette
            "VALIDATION_ERROR",
            "Request validation failed",
            details=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Internal server error",
        )
