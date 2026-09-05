"""Authentication: password hashing (bcrypt) + JWT sessions.

Real accounts (email + password) coexist with the legacy username-only "guest"
flow so nothing breaks. Endpoints can require auth via `current_user` when
REQUIRE_AUTH is on, or accept an optional user via `optional_user`.
"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import db as database
from .config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(password, password_hash)
    except Exception:
        return False


def create_token(user: database.User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def _decode(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        return None


def _user_from_creds(
    creds: HTTPAuthorizationCredentials | None, db: Session
) -> database.User | None:
    if not creds or not creds.credentials:
        return None
    payload = _decode(creds.credentials)
    if not payload:
        return None
    uid = payload.get("sub")
    if uid is None:
        return None
    try:
        return db.get(database.User, int(uid))
    except (TypeError, ValueError):
        return None


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(database.get_db),
) -> database.User | None:
    """Returns the authenticated user if a valid token is present, else None."""
    return _user_from_creds(creds, db)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(database.get_db),
) -> database.User:
    """Requires a valid token when REQUIRE_AUTH is on. When off, this still
    enforces a token IF one is provided but does not block anonymous use — use
    `optional_user` for fully-open endpoints."""
    user = _user_from_creds(creds, db)
    if user is None and settings.REQUIRE_AUTH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
