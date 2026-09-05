"""Curriculum endpoints: company packs, learning paths and spaced-repetition
review queue."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth, curriculum
from .. import db as database
from ..dependencies import require_user

router = APIRouter(tags=["curriculum"])


@router.get("/api/company-packs")
def company_packs():
    return curriculum.list_company_packs()


@router.get("/api/learning-paths")
def learning_paths(
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    paths = curriculum.list_learning_paths()
    if user:
        return [curriculum.path_progress(db, user.id, p) for p in paths]
    return [{**p, "completed": 0, "total": len(p["steps"])} for p in paths]


@router.get("/api/review-queue")
def review_queue(
    user: database.User = Depends(require_user("Log in to see your review queue.")),
    db: Session = Depends(database.get_db),
):
    """Spaced-repetition: concepts the user should review, from past weak areas."""
    return curriculum.review_queue(db, user.id)
