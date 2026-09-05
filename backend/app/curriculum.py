"""Company prep packs, structured learning paths, and spaced-repetition of a
user's weak concepts."""

from datetime import datetime

from sqlalchemy.orm import Session

from . import analytics
from . import db as database

# --------------------------------------------------------------------------- #
# Company prep packs — curated interview presets per company.
# --------------------------------------------------------------------------- #
COMPANY_PACKS = [
    {
        "id": "amazon_lp",
        "company_id": "amazon",
        "name": "Amazon — Leadership Principles",
        "blurb": "Behavioral rounds built around Amazon's 16 LPs (STAR).",
        "sessions": [
            {"track": "sde", "focus": "behavioral", "difficulty": "medium"},
            {"track": "sde", "focus": "behavioral", "difficulty": "hard"},
        ],
    },
    {
        "id": "google_algo",
        "company_id": "google",
        "name": "Google — Algorithms & System Design",
        "blurb": "Google-style DSA depth plus a hard system design round.",
        "sessions": [
            {"track": "sde", "focus": "dsa", "difficulty": "hard"},
            {"track": "sde", "focus": "system_design", "difficulty": "hard"},
        ],
    },
    {
        "id": "meta_fullloop",
        "company_id": "meta",
        "name": "Meta — Full Loop",
        "blurb": "Coding, product-sense system design, and behavioral.",
        "sessions": [
            {"track": "sde", "focus": "dsa", "difficulty": "medium"},
            {"track": "sde", "focus": "system_design", "difficulty": "hard"},
            {"track": "sde", "focus": "behavioral", "difficulty": "medium"},
        ],
    },
    {
        "id": "startup_generalist",
        "company_id": "startup",
        "name": "Startup — Generalist",
        "blurb": "Pragmatic coding + LLD + ownership behavioral.",
        "sessions": [
            {"track": "sde", "focus": "dsa", "difficulty": "medium"},
            {"track": "sde", "focus": "lld", "difficulty": "medium"},
        ],
    },
]


def list_company_packs() -> list[dict]:
    return COMPANY_PACKS


# --------------------------------------------------------------------------- #
# Learning paths — ordered multi-session curricula.
# --------------------------------------------------------------------------- #
LEARNING_PATHS = [
    {
        "id": "sde_foundations",
        "name": "SDE Interview Foundations",
        "blurb": "Build core skills across DSA, LLD and system design.",
        "steps": [
            {"title": "Warm-up DSA", "track": "sde", "focus": "dsa", "difficulty": "easy"},
            {"title": "Core DSA", "track": "sde", "focus": "dsa", "difficulty": "medium"},
            {"title": "Low-level design", "track": "sde", "focus": "lld", "difficulty": "medium"},
            {
                "title": "System design basics",
                "track": "sde",
                "focus": "system_design",
                "difficulty": "medium",
            },
            {"title": "Behavioral", "track": "sde", "focus": "behavioral", "difficulty": "medium"},
        ],
    },
    {
        "id": "sde_senior",
        "name": "Senior/Staff System Design",
        "blurb": "Go deep on hard distributed-systems design.",
        "steps": [
            {
                "title": "Scaling fundamentals",
                "track": "sde",
                "focus": "system_design",
                "difficulty": "medium",
            },
            {
                "title": "Hard design 1",
                "track": "sde",
                "focus": "system_design",
                "difficulty": "hard",
            },
            {
                "title": "Hard design 2",
                "track": "sde",
                "focus": "system_design",
                "difficulty": "hard",
            },
            {
                "title": "Leadership behavioral",
                "track": "sde",
                "focus": "behavioral",
                "difficulty": "hard",
            },
        ],
    },
]


def list_learning_paths() -> list[dict]:
    return LEARNING_PATHS


def path_progress(db: Session, user_id: int, path: dict) -> dict:
    """Mark each step done if the user has a report matching its track+focus."""
    reports = db.query(database.InterviewReport).filter_by(user_id=user_id).all()
    done_keys = {(r.track, r.focus) for r in reports}
    steps = []
    completed = 0
    for s in path["steps"]:
        is_done = (s["track"], s["focus"]) in done_keys
        if is_done:
            completed += 1
        steps.append({**s, "done": is_done})
    return {
        **path,
        "steps": steps,
        "completed": completed,
        "total": len(path["steps"]),
    }


# --------------------------------------------------------------------------- #
# Spaced repetition — resurface weak concepts from the user's history.
# --------------------------------------------------------------------------- #
def review_queue(db: Session, user_id: int) -> dict:
    """Concepts/areas the user struggled with, due for review. Uses their weak
    dimensions and the 'improvements' notes from past reports, weighting older,
    lower-scored areas higher."""
    stats = analytics.compute_stats(db, user_id)
    if stats["total_interviews"] == 0:
        return {"due": [], "weak_dimensions": []}

    # collect improvement notes across reports, most recent first
    reports = (
        db.query(database.InterviewReport)
        .filter_by(user_id=user_id)
        .order_by(database.InterviewReport.created_at.desc())
        .all()
    )
    seen = set()
    due = []
    now = datetime.utcnow()
    for r in reports:
        for imp in r.improvements or []:
            key = imp.strip().lower()
            if key in seen or not key:
                continue
            seen.add(key)
            age_days = (now - r.created_at).days
            # simple spacing: things practiced longer ago are more "due"
            due.append(
                {
                    "concept": imp,
                    "from_focus": r.focus,
                    "last_seen_days": age_days,
                    "score_at_time": r.overall_score,
                }
            )
    # sort by (older + lower score) => higher priority
    due.sort(key=lambda d: (d["score_at_time"], -d["last_seen_days"]))
    return {
        "due": due[:12],
        "weak_dimensions": stats["weak_areas"],
    }
