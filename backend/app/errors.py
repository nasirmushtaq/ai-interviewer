"""Domain-level errors and their HTTP mapping.

Routers raise FastAPI's ``HTTPException`` for pure transport concerns (auth,
validation, 404s tied to a URL). The *service layer* — which must stay ignorant
of HTTP — instead raises the ``AppError`` subclasses below, and a single handler
registered on the app maps them to responses. This keeps business logic free of
``fastapi`` imports while still yielding consistent, well-formed error bodies.
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

log = logging.getLogger("linguacall")


class AppError(Exception):
    """Base class for expected, client-reportable failures in the service layer."""

    status_code: int = 500
    detail: str = "Internal server error."

    def __init__(self, detail: str | None = None):
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotConfiguredError(AppError):
    """A required capability (LLM provider, realtime voice) is not configured."""

    status_code = 400


class UpstreamError(AppError):
    """A dependency we call out to (e.g. the LLM provider) failed."""

    status_code = 502


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the app's exception handlers. Called once from the app factory."""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please slow down and retry."},
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        rid = uuid.uuid4().hex[:8]
        log.exception("unhandled error [%s] on %s %s", rid, request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error (ref {rid})."},
        )
