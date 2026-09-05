"""LinguaCall API — application factory.

Thin composition root: configure logging, build the FastAPI app, attach
middleware, error handlers and every domain router. All request handling lives
in :mod:`app.routers`; all orchestration in the service modules.
"""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .errors import register_exception_handlers
from .lifespan import lifespan
from .ratelimit import limiter
from .routers import ALL_ROUTERS

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("linguacall")


def create_app() -> FastAPI:
    app = FastAPI(title="LinguaCall API", version="1.0.0", lifespan=lifespan)
    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _access_log(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        dur = (time.time() - start) * 1000
        log.info(
            "%s %s -> %s (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            dur,
        )
        return response

    register_exception_handlers(app)

    for router in ALL_ROUTERS:
        app.include_router(router)

    return app


app = create_app()
