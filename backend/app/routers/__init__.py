"""HTTP routers, grouped by domain.

``ALL_ROUTERS`` is the single list the app factory iterates over to wire the API,
so adding a new domain is a one-line change here plus a new module.
"""

from ..billing_routes import router as billing_router
from ..sessions import router as sessions_router
from . import (
    auth_routes,
    conversations,
    curriculum_routes,
    dashboard,
    history,
    interview,
    meta,
    resume_routes,
)

ALL_ROUTERS = [
    meta.router,
    auth_routes.router,
    interview.router,
    conversations.router,
    dashboard.router,
    curriculum_routes.router,
    resume_routes.router,
    history.router,
    sessions_router,
    billing_router,
]

__all__ = ["ALL_ROUTERS"]
