"""The authenticated user's activity history: conversations, memories, reports."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import db as database
from ..dependencies import require_user

router = APIRouter(tags=["history"])


@router.get("/api/history/{username}")
def history(
    username: str,
    db: Session = Depends(database.get_db),
    user: database.User = Depends(require_user("Log in to view your history.")),
):
    # SECURITY: you may only read YOUR OWN history. The {username} in the path is
    # ignored for authorization — we serve the authenticated user's data. (Kept in
    # the path only for backward-compatible client URLs.)
    convos = (
        db.query(database.Conversation)
        .filter_by(user_id=user.id)
        .order_by(database.Conversation.created_at.desc())
        .all()
    )
    mems = (
        db.query(database.Memory)
        .filter_by(user_id=user.id)
        .order_by(database.Memory.created_at.desc())
        .all()
    )
    reports = (
        db.query(database.InterviewReport)
        .filter_by(user_id=user.id)
        .order_by(database.InterviewReport.created_at.desc())
        .all()
    )
    return {
        "conversations": [
            {
                "id": c.id,
                "mode": c.mode,
                "persona_id": c.persona_id,
                "title": c.title,
                "summary": c.summary,
                "created_at": c.created_at.isoformat(),
            }
            for c in convos
        ],
        "memories": [{"id": m.id, "persona_id": m.persona_id, "fact": m.fact} for m in mems],
        "reports": [
            {
                "id": r.id,
                "role": r.role,
                "track": r.track,
                "focus": r.focus,
                "difficulty": r.difficulty,
                "company": r.company,
                "overall_score": r.overall_score,
                "hints_used": r.hints_used,
                "hint_penalty": r.hint_penalty,
                "scores": r.scores,
                "strengths": r.strengths,
                "improvements": r.improvements,
                "feedback": r.feedback,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ],
    }
