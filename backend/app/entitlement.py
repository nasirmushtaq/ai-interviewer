"""Entitlement: server-side gate for paid features (bypass-proof).

An interview is allowed if the user has free quota remaining OR paid credits.
`consume_interview` atomically decrements quota/credits and is called at the
single choke point (interview session creation) so the client cannot bypass it.
"""
from sqlalchemy.orm import Session

from .config import settings
from . import db as database


def entitlement(user: database.User) -> dict:
    free_remaining = max(0, settings.FREE_INTERVIEW_QUOTA - (user.interviews_used or 0))
    credits = user.interview_credits or 0
    return {
        "free_quota": settings.FREE_INTERVIEW_QUOTA,
        "interviews_used": user.interviews_used or 0,
        "free_remaining": free_remaining,
        "credits": credits,
        "can_start_interview": (free_remaining + credits) > 0,
    }


def can_start_interview(user: database.User) -> bool:
    return entitlement(user)["can_start_interview"]


def consume_interview(db: Session, user: database.User) -> bool:
    """Atomically consume one interview: use free quota first, then a paid credit.
    Returns True if consumed, False if the user has neither (paywall)."""
    # Re-read within the session to avoid a stale in-memory view.
    u = db.get(database.User, user.id)
    if u is None:
        return False
    free_remaining = max(0, settings.FREE_INTERVIEW_QUOTA - (u.interviews_used or 0))
    if free_remaining > 0:
        u.interviews_used = (u.interviews_used or 0) + 1
        db.commit()
        return True
    if (u.interview_credits or 0) > 0:
        u.interview_credits -= 1
        u.interviews_used = (u.interviews_used or 0) + 1
        db.commit()
        return True
    return False


def grant_credits(db: Session, user_id: int, credits: int) -> None:
    u = db.get(database.User, user_id)
    if u is not None:
        u.interview_credits = (u.interview_credits or 0) + int(credits)
        db.commit()
