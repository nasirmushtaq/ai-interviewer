"""Reusable FastAPI dependencies.

Centralises the two patterns that were previously copy-pasted across handlers:
resolving/creating a guest user, and requiring an authenticated user with a
context-specific 401 message.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from . import auth
from . import db as database
from .config import settings


def get_or_create_user(db: Session, username: str) -> database.User:
    """Resolve a guest user by username, creating it on first use.

    Guest usernames (client-supplied, no real auth) are a dev/staging-only
    convenience. In production every action must be tied to an authenticated
    account, so this path is hard-disabled there — guarding the helper covers
    every call site (current and future) at a single choke point.
    """
    if settings.is_production:
        raise HTTPException(401, "Authentication required.")
    username = (username or "guest").strip().lower()
    user = db.query(database.User).filter_by(username=username).first()
    if not user:
        user = database.User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def require_user(detail: str = "Not authenticated.") -> Callable[..., database.User]:
    """Build a dependency that yields the authenticated user or raises 401.

    Usage::

        user: database.User = Depends(require_user("Log in to see your progress."))
    """

    def _dependency(
        user: database.User | None = Depends(auth.optional_user),
    ) -> database.User:
        if not user:
            raise HTTPException(401, detail)
        return user

    return _dependency
