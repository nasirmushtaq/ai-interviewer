"""Application lifespan: startup safety guards and dev-time DB bootstrap.

Replaces the deprecated ``@app.on_event("startup")`` hook with an ASGI lifespan
context manager (the supported API in modern FastAPI/Starlette).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db as database
from . import openai_service as ai
from .config import settings

log = logging.getLogger("linguacall")


def _production_config_problems() -> list[str]:
    """Return a list of fatal misconfigurations for a production deployment."""
    problems: list[str] = []
    if settings.JWT_SECRET == "dev-insecure-change-me" or len(settings.JWT_SECRET) < 16:
        problems.append(
            "JWT_SECRET is the insecure default or too short — set a strong "
            "random secret (e.g. `openssl rand -hex 32`). Refusing to start."
        )
    if "*" in settings.cors_origins_list():
        problems.append(
            "CORS_ORIGINS is '*' in production — set it to your exact frontend "
            "origin(s). Refusing to start."
        )
    if not ai.has_key():
        problems.append("No LLM provider is configured. Refusing to start.")
    return problems


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # --- Production safety guards: fail fast on insecure/incomplete config. ---
    if settings.is_production:
        problems = _production_config_problems()
        if problems:
            for problem in problems:
                log.error("STARTUP BLOCKED: %s", problem)
            raise RuntimeError(
                "Refusing to start in production with insecure config:\n- " + "\n- ".join(problems)
            )

    # The SQLAlchemy models are the single source of truth for the schema: create
    # any missing tables on startup (idempotent — never drops or alters). The app
    # is pre-launch, so there are no migrations to reconcile. Once live and
    # evolving a populated schema, introduce a migration tool (e.g. Alembic) and
    # gate this behind dev-only.
    database.init_db()

    log.info(
        "LinguaCall API starting: env=%s provider=%s vision=%s realtime=%s db=%s",
        settings.ENV,
        settings.provider,
        settings.vision_provider(),
        ai.realtime_available(),
        settings.DATABASE_URL.split("://", 1)[0],
    )
    yield
