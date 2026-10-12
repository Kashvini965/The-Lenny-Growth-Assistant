"""Structured error types and FastAPI exception handlers.

All API errors share one envelope shape so the frontend can render them
uniformly:

```json
{ "error": { "code": "not_found", "message": "...", "details": {...} } }
```
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, user-facing application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationAppError(AppError):
    status_code: int = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
    code = "validation_error"


class ProviderUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "provider_unavailable"


class ProviderTimeoutError(AppError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    code = "provider_timeout"


class ProviderConfigError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "provider_not_configured"


class DatabaseUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "database_unavailable"


class ArtifactError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "artifact_error"


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the handlers onto the FastAPI app."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError [%s]: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            content=_envelope(
                "validation_error",
                "Request payload failed validation.",
                {"errors": _jsonable_errors(exc.errors())},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(f"http_{exc.status_code}", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred."),
        )


def _jsonable_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`exc.errors()` may contain non-serialisable values (e.g. ValueError)."""
    safe: list[dict[str, Any]] = []
    for err in errors:
        clean = {k: v for k, v in err.items() if k != "ctx"}
        clean["loc"] = [str(part) for part in err.get("loc", [])]
        clean["msg"] = str(err.get("msg", ""))
        clean["type"] = str(err.get("type", ""))
        safe.append(clean)
    return safe
