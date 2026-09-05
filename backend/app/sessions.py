"""Session lifecycle + media/vision observation endpoints.

A client (web or native) creates a session, connects its voice call and its
camera/screen media (via the Node media service), and the media service POSTs
sampled frames here for GPT-4o vision analysis. Observations are persisted and
also fanned out live over a WebSocket so the client can display "the interviewer
noticed X" and, if desired, nudge the realtime agent.
"""

import asyncio
import uuid
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from . import auth, catalog, entitlement, execution, problems, pubsub, services, vision_service
from . import db as database
from .config import settings
from .ratelimit import limiter

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Live observation pub/sub (Redis-backed, in-memory fallback).
hub = pubsub.get_pubsub()


def _require_media_token(x_media_token: str | None) -> None:
    if x_media_token != settings.MEDIA_SERVICE_TOKEN:
        raise HTTPException(401, "Invalid media service token.")


def _get_user(db: DbSession, username: str) -> database.User:
    username = (username or "guest").strip().lower()
    user = db.query(database.User).filter_by(username=username).first()
    if not user:
        user = database.User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ---------- schemas ----------
class StartSessionIn(BaseModel):
    username: str
    mode: str = "interview"  # interview | persona
    persona_id: str | None = None
    track: str | None = "sde"
    role: str | None = "SDE"
    focus: str | None = "dsa"
    difficulty: str | None = "medium"
    company_id: str | None = None
    company_name: str | None = None
    hints_enabled: bool = True


class FrameIn(BaseModel):
    source: str  # "camera" | "screen"
    image: str  # data URL (data:image/jpeg;base64,....)
    hint: str | None = None


class EndSessionIn(BaseModel):
    transcript: list[dict] = []


class HintIn(BaseModel):
    tier: int = 1  # 1 nudge, 2 approach, 3 partial solution
    question_context: str | None = None
    transcript: list[dict] = []


# ---------- lifecycle ----------
@router.post("")
def start_session(
    body: StartSessionIn,
    db: DbSession = Depends(database.get_db),
    authed: database.User | None = Depends(auth.optional_user),
):
    # Feature-flag enforcement (server-side, so disabled features can't be
    # started via a direct API call regardless of the UI).
    if body.mode == "persona" and not settings.ENABLE_PERSONA_CALLS:
        raise HTTPException(403, "Persona calls are currently unavailable.")
    if body.mode == "interview" and not settings.is_track_enabled(body.track):
        raise HTTPException(403, f"The '{body.track}' track is currently unavailable.")

    # Interview mode is a PAID feature gated server-side (bypass-proof):
    #   1) must be an authenticated account (not a client-supplied username), and
    #   2) must have free quota or paid credits — consumed atomically here.
    # Persona/practice mode stays open to guests.
    if body.mode == "interview":
        if authed is None:
            raise HTTPException(401, "Please log in to start an interview.")
        user = authed
        if not entitlement.consume_interview(db, user):
            e = entitlement.entitlement(user)
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "You've used your free interviews. Buy credits to continue.",
                    "entitlement": e,
                },
            )
    else:
        user = authed or _get_user(db, body.username)

    sess = database.Session(
        id=uuid.uuid4().hex,
        user_id=user.id,
        mode=body.mode,
        persona_id=body.persona_id,
        track=body.track,
        role=body.role,
        focus=body.focus,
        difficulty=body.difficulty,
        company_id=body.company_id,
        company_name=body.company_name,
        hints_enabled=body.hints_enabled,
        status="active",
        transcript=[],
    )
    db.add(sess)
    db.commit()
    return {
        "session_id": sess.id,
        "media_service_url": settings.MEDIA_SERVICE_URL,
        "status": sess.status,
        "entitlement": entitlement.entitlement(user),
    }


@router.get("/{session_id}")
def get_session(session_id: str, db: DbSession = Depends(database.get_db)):
    sess = db.get(database.Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found.")
    return {
        "session_id": sess.id,
        "mode": sess.mode,
        "status": sess.status,
        "track": sess.track,
        "role": sess.role,
        "focus": sess.focus,
        "difficulty": sess.difficulty,
        "company_id": sess.company_id,
        "company_name": sess.company_name,
        "hints_enabled": sess.hints_enabled,
        "hints_used": len(sess.hints),
        "hint_penalty": sum(h.penalty for h in sess.hints),
        "observations": [
            {"source": o.source, "note": o.note, "flags": o.flags, "at": o.created_at.isoformat()}
            for o in sess.observations
        ],
    }


# ---------- frame ingestion (called by the media service) ----------
@router.post("/{session_id}/frames")
async def ingest_frame(
    session_id: str,
    body: FrameIn,
    db: DbSession = Depends(database.get_db),
    x_media_token: str | None = Header(default=None),
):
    _require_media_token(x_media_token)
    sess = db.get(database.Session, session_id)
    if not sess or sess.status != "active":
        raise HTTPException(404, "Active session not found.")
    if body.source not in ("camera", "screen"):
        raise HTTPException(400, "source must be 'camera' or 'screen'.")

    result = await asyncio.to_thread(
        vision_service.analyze_frame, body.source, body.image, body.hint or ""
    )
    obs = database.Observation(
        session_id=session_id,
        source=body.source,
        note=result["note"],
        flags=result["flags"],
    )
    db.add(obs)
    db.commit()

    payload = {
        "type": "observation",
        "source": body.source,
        "note": result["note"],
        "flags": result["flags"],
        "at": datetime.utcnow().isoformat(),
    }
    await hub.publish(session_id, payload)
    return payload


# ---------- tiered hints (candidate-requested; cost score) ----------
@router.post("/{session_id}/hint")
@limiter.limit(settings.RATE_LIMIT_LLM)
async def request_hint(
    request: Request, session_id: str, body: HintIn, db: DbSession = Depends(database.get_db)
):
    sess = db.get(database.Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found.")
    if not sess.hints_enabled:
        raise HTTPException(403, "Hints are disabled for this session.")

    tier, spec = catalog.resolve_hint_tier(body.tier)
    text = await asyncio.to_thread(
        services.generate_hint,
        tier,
        spec["reveal"],
        body.question_context or "",
        body.transcript or sess.transcript or [],
        sess.role or "SDE",
        sess.focus or "dsa",
        sess.track,
    )
    hint = database.Hint(
        session_id=session_id,
        tier=tier,
        penalty=spec["penalty"],
        question_context=(body.question_context or "")[:500],
        text=text,
    )
    db.add(hint)
    db.commit()

    used = db.query(database.Hint).filter_by(session_id=session_id).count()
    total_penalty = sum(
        h.penalty for h in db.query(database.Hint).filter_by(session_id=session_id).all()
    )
    return {
        "tier": tier,
        "label": spec["label"],
        "penalty": spec["penalty"],
        "text": text,
        "hints_used": used,
        "total_penalty": total_penalty,
    }


# ---------- live observation stream (consumed by clients) ----------
@router.websocket("/{session_id}/observe")
async def observe(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        await websocket.send_json({"type": "connected", "session_id": session_id})
        async for msg in hub.subscription(session_id):
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ============================ Coding round ============================
class ProblemIn(BaseModel):
    seed_id: str | None = None
    topic: str | None = None


class RunIn(BaseModel):
    language: str
    source: str


class SubmitIn(BaseModel):
    language: str
    source: str


def _problem_for_client(p: dict) -> dict:
    """Never leak hidden tests to the client."""
    return {
        "id": p.get("id"),
        "title": p.get("title"),
        "difficulty": p.get("difficulty"),
        "statement": p.get("statement"),
        "starter": p.get("starter", {}),
        "examples": p.get("examples", []),
        "hidden_count": len(p.get("hidden", []) or []),
    }


@router.post("/{session_id}/problem")
def get_problem(session_id: str, body: ProblemIn, db: DbSession = Depends(database.get_db)):
    sess = db.get(database.Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found.")
    company = catalog.resolve_company(sess.company_id, sess.company_name)
    problem = problems.pick_problem(
        difficulty=sess.difficulty or "medium",
        focus=sess.focus or "dsa",
        company=company["name"],
        topic=body.topic,
        prefer_seed_id=body.seed_id,
    )
    sess.problem = problem
    db.commit()
    return _problem_for_client(problem)


@router.get("/{session_id}/problem")
def current_problem(session_id: str, db: DbSession = Depends(database.get_db)):
    sess = db.get(database.Session, session_id)
    if not sess or not sess.problem:
        raise HTTPException(404, "No problem set for this session yet.")
    return _problem_for_client(sess.problem)


@router.get("/coding/languages")
def coding_languages():
    return execution.list_languages()


@router.post("/{session_id}/run")
@limiter.limit(settings.RATE_LIMIT_EXEC)
def run_code(
    request: Request, session_id: str, body: RunIn, db: DbSession = Depends(database.get_db)
):
    """Run against VISIBLE example tests only; return full details."""
    sess = db.get(database.Session, session_id)
    if not sess or not sess.problem:
        raise HTTPException(404, "No active problem.")
    if not execution.available():
        raise HTTPException(503, "Code execution service (Judge0) is not reachable.")
    examples = sess.problem.get("examples", [])
    result = execution.run_tests(body.language, body.source, examples)
    sess.code_language = body.language
    sess.code_source = body.source
    db.commit()
    return result


@router.post("/{session_id}/submit")
@limiter.limit(settings.RATE_LIMIT_EXEC)
def submit_code(
    request: Request, session_id: str, body: SubmitIn, db: DbSession = Depends(database.get_db)
):
    """Run against example + hidden tests. Hidden inputs are NOT returned —
    only aggregate pass/fail so the candidate can't reverse-engineer them."""
    sess = db.get(database.Session, session_id)
    if not sess or not sess.problem:
        raise HTTPException(404, "No active problem.")
    if not execution.available():
        raise HTTPException(503, "Code execution service (Judge0) is not reachable.")
    examples = sess.problem.get("examples", [])
    hidden = sess.problem.get("hidden", []) or []
    all_tests = examples + hidden
    result = execution.run_tests(body.language, body.source, all_tests)

    # Redact hidden test details for the client response.
    client_results = []
    for r in result.get("results", []):
        if r.get("hidden"):
            client_results.append(
                {
                    "hidden": True,
                    "passed": r["passed"],
                    "status": r["status"],
                }
            )
        else:
            client_results.append(r)

    ex_passed = sum(1 for r in result["results"][: len(examples)] if r["passed"])
    hid_passed = sum(1 for r in result["results"][len(examples) :] if r["passed"])
    summary = {
        "results": client_results,
        "example_passed": ex_passed,
        "example_total": len(examples),
        "hidden_passed": hid_passed,
        "hidden_total": len(hidden),
        "passed": result["passed"],
        "total": result["total"],
    }
    sess.code_language = body.language
    sess.code_source = body.source
    sess.code_result = summary
    db.commit()
    return summary


# ============================ Design whiteboard ============================
class DiagramIn(BaseModel):
    image: str  # data URL PNG snapshot of the whiteboard
    structure: dict | None = None  # extracted components + edges graph
    final: bool = False


@router.post("/{session_id}/diagram")
async def submit_diagram(
    session_id: str, body: DiagramIn, db: DbSession = Depends(database.get_db)
):
    """Structured architectural analysis of the whiteboard: builds a graph model,
    diffs it against the previous version, runs GPT-4o vision on the graph+image,
    and stores the reading so the interviewer can adaptively probe it."""
    sess = db.get(database.Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found.")

    prev_model = sess.diagram_model
    curr_model = body.structure or {}

    # What changed since last update (added/removed components & connections).
    diff = vision_service.diff_models(prev_model, curr_model)
    change_text = vision_service.diff_to_text(diff) if vision_service.has_changes(diff) else ""

    analysis = await asyncio.to_thread(
        vision_service.analyze_architecture,
        body.image,
        curr_model,
        "This is the candidate's live system-design whiteboard.",
    )
    if change_text:
        analysis["last_change"] = change_text

    sess.diagram_model = curr_model
    sess.diagram_analysis = analysis
    if body.final:
        sess.diagram_snapshot = body.image

    # Decide whether this change warrants the interviewer speaking up NOW.
    # Silent by default — only meaningful changes trigger a proactive follow-up.
    reaction = {"react": False, "message": ""}
    if change_text:
        recent = "\n".join(
            f"{t.get('role')}: {t.get('text','')}" for t in (sess.transcript or [])[-6:]
        )
        reaction = await asyncio.to_thread(
            vision_service.decide_reaction, diff, curr_model, analysis, recent
        )
        if reaction.get("react") and reaction.get("message"):
            # Record the interviewer's proactive interjection into the transcript
            # so the conversation stays coherent.
            tr = list(sess.transcript or [])
            tr.append({"role": "assistant", "text": reaction["message"]})
            sess.transcript = tr

    # Record an observation (summary + gaps) for the transcript/grader.
    note = analysis.get("summary", "")
    if analysis.get("gaps"):
        note += " | gaps: " + "; ".join(analysis["gaps"])
    db.add(
        database.Observation(
            session_id=session_id,
            source="diagram",
            note=note,
            flags=analysis.get("flags", []),
        )
    )
    db.commit()

    payload = {
        "type": "observation",
        "source": "diagram",
        "note": analysis.get("summary", ""),
        "gaps": analysis.get("gaps", []),
        "change": change_text,
        "flags": analysis.get("flags", []),
        "at": datetime.utcnow().isoformat(),
    }
    await hub.publish(session_id, payload)
    return {
        "summary": analysis.get("summary", ""),
        "components": analysis.get("components", []),
        "data_flows": analysis.get("data_flows", []),
        "gaps": analysis.get("gaps", []),
        "change": change_text,
        "flags": analysis.get("flags", []),
        # Only present when the interviewer should proactively speak up.
        "reaction": reaction.get("message", "") if reaction.get("react") else "",
    }
