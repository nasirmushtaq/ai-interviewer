"""Dashboard endpoints: personal progress stats, leaderboards and interview
replays."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import analytics, auth
from .. import db as database
from .. import leaderboard as lb
from ..dependencies import require_user

router = APIRouter(tags=["dashboard"])


@router.get("/api/stats")
def stats(
    user: database.User = Depends(require_user("Log in to see your progress.")),
    db: Session = Depends(database.get_db),
):
    """Personal progress analytics: trends, weak areas, streaks. Requires login."""
    return analytics.compute_stats(db, user.id)


@router.get("/api/leaderboard")
def leaderboard_endpoint(
    track: str | None = None,
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    """Global or per-track leaderboard by best score. Everyone auto-listed."""
    return lb.leaderboard(db, track=track, me_id=user.id if user else None)


@router.get("/api/challenge")
def challenge_endpoint(
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    """This week's shared challenge + its leaderboard."""
    return lb.challenge_leaderboard(db, me_id=user.id if user else None)


@router.get("/api/replay/{report_id}")
def replay(
    report_id: int,
    user: database.User = Depends(require_user("Log in to view recordings.")),
    db: Session = Depends(database.get_db),
):
    """Full recording of a past interview: report + transcript + code + diagram."""
    rep = db.get(database.InterviewReport, report_id)
    if not rep or rep.user_id != user.id:
        raise HTTPException(404, "Recording not found.")
    sess = db.get(database.Session, rep.session_id) if rep.session_id else None
    return {
        "report": {
            "id": rep.id,
            "role": rep.role,
            "track": rep.track,
            "focus": rep.focus,
            "difficulty": rep.difficulty,
            "company": rep.company,
            "overall_score": rep.overall_score,
            "scores": rep.scores,
            "strengths": rep.strengths,
            "improvements": rep.improvements,
            "feedback": rep.feedback,
            "hints_used": rep.hints_used,
            "created_at": rep.created_at.isoformat(),
        },
        "transcript": (sess.transcript if sess else []) or [],
        "code": {
            "language": sess.code_language if sess else None,
            "source": sess.code_source if sess else None,
            "result": sess.code_result if sess else None,
        },
        "diagram": sess.diagram_snapshot if sess else None,
    }
