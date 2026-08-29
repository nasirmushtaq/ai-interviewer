"""Progress analytics computed from a user's interview reports:
score trends over time, per-dimension averages + weak areas, and streaks.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import db as database

DIMENSIONS = ["problem_solving", "technical_depth", "communication", "correctness"]
DIM_LABELS = {
    "problem_solving": "Problem Solving",
    "technical_depth": "Technical Depth",
    "communication": "Communication",
    "correctness": "Correctness",
}


def _reports(db: Session, user_id: int) -> list[database.InterviewReport]:
    return (
        db.query(database.InterviewReport)
        .filter_by(user_id=user_id)
        .order_by(database.InterviewReport.created_at.asc())
        .all()
    )


def compute_stats(db: Session, user_id: int) -> dict:
    reports = _reports(db, user_id)
    if not reports:
        return {
            "total_interviews": 0,
            "trend": [],
            "dimensions": [],
            "weak_areas": [],
            "strong_areas": [],
            "by_track": [],
            "streak": {"current": 0, "longest": 0, "active_days": 0},
            "average_score": 0,
            "best_score": 0,
            "recent_improvement": 0,
        }

    # ---- score trend over time ----
    trend = [
        {
            "id": r.id,
            "date": r.created_at.isoformat(),
            "score": r.overall_score,
            "track": r.track,
            "focus": r.focus,
            "company": r.company,
            "difficulty": r.difficulty,
        }
        for r in reports
    ]

    scores = [r.overall_score for r in reports]
    average_score = round(sum(scores) / len(scores))
    best_score = max(scores)

    # recent improvement: avg of last 3 vs first 3
    if len(scores) >= 2:
        head = scores[: min(3, len(scores) // 2 or 1)]
        tail = scores[-min(3, len(scores) // 2 or 1):]
        recent_improvement = round(sum(tail) / len(tail) - sum(head) / len(head))
    else:
        recent_improvement = 0

    # ---- per-dimension averages (weak-area heatmap) ----
    dim_totals: dict[str, list[int]] = {d: [] for d in DIMENSIONS}
    for r in reports:
        s = r.scores or {}
        for d in DIMENSIONS:
            v = s.get(d)
            if isinstance(v, (int, float)):
                dim_totals[d].append(int(v))
    dimensions = []
    for d in DIMENSIONS:
        vals = dim_totals[d]
        if vals:
            dimensions.append({
                "id": d,
                "label": DIM_LABELS[d],
                "average": round(sum(vals) / len(vals)),
                "count": len(vals),
            })
    ranked = sorted(dimensions, key=lambda x: x["average"])
    weak_areas = [d for d in ranked[:2]] if ranked else []
    strong_areas = [d for d in ranked[-2:][::-1]] if ranked else []

    # ---- per-track breakdown ----
    track_map: dict[str, list[int]] = {}
    for r in reports:
        track_map.setdefault(r.track or "other", []).append(r.overall_score)
    by_track = [
        {
            "track": t,
            "count": len(v),
            "average": round(sum(v) / len(v)),
            "best": max(v),
        }
        for t, v in track_map.items()
    ]

    # ---- streaks (consecutive days with >=1 interview) ----
    days = sorted({r.created_at.date() for r in reports})
    active_days = len(days)
    longest = current = 1 if days else 0
    for i in range(1, len(days)):
        if days[i] - days[i - 1] == timedelta(days=1):
            current += 1
        else:
            current = 1
        longest = max(longest, current)
    # current streak counts back from today/yesterday
    today = datetime.utcnow().date()
    cur_streak = 0
    if days:
        expect = today
        dayset = set(days)
        # allow the streak to be "current" if the last activity was today or yesterday
        if days[-1] in (today, today - timedelta(days=1)):
            expect = days[-1]
            while expect in dayset:
                cur_streak += 1
                expect -= timedelta(days=1)

    return {
        "total_interviews": len(reports),
        "trend": trend,
        "dimensions": dimensions,
        "weak_areas": weak_areas,
        "strong_areas": strong_areas,
        "by_track": by_track,
        "streak": {
            "current": cur_streak,
            "longest": longest,
            "active_days": active_days,
        },
        "average_score": average_score,
        "best_score": best_score,
        "recent_improvement": recent_improvement,
    }
