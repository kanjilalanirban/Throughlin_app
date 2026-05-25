"""Error wrappers + exception handlers.

Rule from security.md: never return raw exception messages to clients. Wrap
exceptions here and return generic messages with a correlation ID for support.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for known/expected application errors that map to HTTP codes."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class Unauthorized(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class BadRequest(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"


def _correlation_id(request: Request) -> str:
    """Return the per-request correlation id (set by middleware in main.py)."""
    cid = getattr(request.state, "correlation_id", None)
    return cid or str(uuid.uuid4())


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    cid = _correlation_id(request)
    logger.warning(
        "app error",
        extra={"code": exc.code, "status": exc.status_code, "correlation_id": cid, "path": request.url.path},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": str(exc), "correlation_id": cid},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    cid = _correlation_id(request)
    # Full exception with stack trace goes to CloudWatch only.
    logger.exception(
        "unhandled exception",
        extra={"correlation_id": cid, "path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Reference this correlation ID when contacting support.",
            "correlation_id": cid,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the handlers into the FastAPI app. Called from main.py."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
