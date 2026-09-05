"""Authentication endpoints: legacy guest login plus real email + password auth."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import auth
from .. import db as database
from ..config import settings
from ..dependencies import get_or_create_user
from ..ratelimit import limiter
from ..schemas import AuthLoginIn, LoginIn, RegisterIn

log = logging.getLogger("linguacall")
router = APIRouter(tags=["auth"])


def _auth_response(user: database.User) -> dict:
    return {
        "token": auth.create_token(user),
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.post("/api/login")
def login(body: LoginIn, db: Session = Depends(database.get_db)):
    """Legacy guest login (username only). Kept for backward compatibility; new
    clients should use /api/auth/*. DISABLED in production — it would let anyone
    obtain a token for any username."""
    if settings.is_production:
        raise HTTPException(410, "Use /api/auth/register or /api/auth/login.")
    user = get_or_create_user(db, body.username)
    return {"id": user.id, "username": user.username, "token": auth.create_token(user)}


@router.post("/api/auth/register")
@limiter.limit(settings.RATE_LIMIT_AUTH)
def auth_register(request: Request, body: RegisterIn, db: Session = Depends(database.get_db)):
    email = body.email.lower().strip()
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if db.query(database.User).filter_by(email=email).first():
        raise HTTPException(409, "An account with this email already exists.")
    username = (body.username or email.split("@")[0]).strip().lower()
    # Ensure username uniqueness.
    base = username
    n = 1
    while db.query(database.User).filter_by(username=username).first():
        n += 1
        username = f"{base}{n}"
    user = database.User(
        username=username, email=email, password_hash=auth.hash_password(body.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("new user registered: %s", email)
    return _auth_response(user)


@router.post("/api/auth/login")
@limiter.limit(settings.RATE_LIMIT_AUTH)
def auth_login(request: Request, body: AuthLoginIn, db: Session = Depends(database.get_db)):
    email = body.email.lower().strip()
    user = db.query(database.User).filter_by(email=email).first()
    if (
        not user
        or not user.password_hash
        or not auth.verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(401, "Invalid email or password.")
    return _auth_response(user)


@router.get("/api/auth/me")
def auth_me(user: database.User | None = Depends(auth.optional_user)):
    if not user:
        raise HTTPException(401, "Not authenticated.")
    return {"id": user.id, "username": user.username, "email": user.email}
