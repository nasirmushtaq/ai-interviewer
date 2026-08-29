"""Leaderboards (global + per-track) and a weekly challenge.

Ranking is by the user's BEST overall_score (optionally within a track or within
the current challenge week). Everyone with at least one report is auto-listed by
username. Uses existing InterviewReport data — no extra tables needed for the
core leaderboard.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import db as database

# A rotating weekly design/DSA theme so everyone practices the same thing.
CHALLENGE_POOL = [
    {"track": "sde", "focus": "system_design", "title": "Design a rate limiter",
     "prompt": "Design a distributed rate limiter (per-user, global) at scale."},
    {"track": "sde", "focus": "system_design", "title": "Design a URL shortener",
     "prompt": "Design a globally distributed URL shortener like bit.ly."},
    {"track": "sde", "focus": "dsa", "title": "Graphs week",
     "prompt": "Focus: graph algorithms (BFS/DFS, shortest paths, union-find)."},
    {"track": "sde", "focus": "system_design", "title": "Design a news feed",
     "prompt": "Design a social media news feed (fan-out on write vs read)."},
    {"track": "sde", "focus": "lld", "title": "Design a parking lot",
     "prompt": "Low-level design of a parking lot system (OOP, patterns)."},
]


def _week_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def current_challenge() -> dict:
    ws = _week_start()
    # deterministic weekly rotation
    idx = (ws.toordinal() // 7) % len(CHALLENGE_POOL)
    c = CHALLENGE_POOL[idx]
    return {
        **c,
        "week_start": ws.isoformat(),
        "week_end": (ws + timedelta(days=7)).isoformat(),
    }


def _rank_query(db: Session, track: str | None, since: datetime | None):
    q = db.query(
        database.InterviewReport.user_id,
        func.max(database.InterviewReport.overall_score).label("best"),
        func.count(database.InterviewReport.id).label("count"),
    )
    if track:
        q = q.filter(database.InterviewReport.track == track)
    if since:
        q = q.filter(database.InterviewReport.created_at >= since)
    q = q.group_by(database.InterviewReport.user_id).order_by(func.max(
        database.InterviewReport.overall_score).desc())
    return q


def _rows_to_board(db: Session, rows, limit: int, me_id: int | None) -> dict:
    entries = []
    my_rank = None
    for i, (uid, best, count) in enumerate(rows):
        rank = i + 1
        if uid == me_id:
            my_rank = rank
        if rank <= limit:
            user = db.get(database.User, uid)
            entries.append({
                "rank": rank,
                "username": (user.username if user else "user"),
                "best_score": int(best),
                "interviews": int(count),
                "is_me": uid == me_id,
            })
    return {"entries": entries, "my_rank": my_rank}


def leaderboard(db: Session, track: str | None = None, limit: int = 50,
                me_id: int | None = None) -> dict:
    rows = _rank_query(db, track, None).all()
    return _rows_to_board(db, rows, limit, me_id)


def challenge_leaderboard(db: Session, limit: int = 50, me_id: int | None = None) -> dict:
    ch = current_challenge()
    ws = datetime.fromisoformat(ch["week_start"])
    rows = _rank_query(db, ch["track"], ws).all()
    board = _rows_to_board(db, rows, limit, me_id)
    board["challenge"] = ch
    return board
