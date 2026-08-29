import logging
import time
import uuid

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import settings
from . import db as database
from . import openai_service as ai
from . import personas as p
from . import services
from . import vision_service
from . import catalog
from . import auth
from . import analytics
from . import resume as resume_mod
from . import leaderboard as lb
from . import curriculum
from . import coverage
from .ratelimit import limiter
from .sessions import router as sessions_router
from .billing_routes import router as billing_router

# ---------- logging ----------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("linguacall")

app = FastAPI(title="LinguaCall API", version="1.0.0")
app.state.limiter = limiter

app.include_router(sessions_router)
app.include_router(billing_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down and retry."},
    )


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception):
    rid = uuid.uuid4().hex[:8]
    log.exception("unhandled error [%s] on %s %s", rid, request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error (ref {rid})."},
    )


@app.middleware("http")
async def _access_log(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    dur = (time.time() - start) * 1000
    log.info(
        "%s %s -> %s (%.0fms)",
        request.method, request.url.path, response.status_code, dur,
    )
    return response


@app.on_event("startup")
def _startup():
    # Dev convenience: auto-create tables on SQLite. In production, run
    # `alembic upgrade head` (the entrypoint/deploy script does this) and do NOT
    # auto-create, so migrations remain the single source of truth.
    if not settings.is_production and settings.DATABASE_URL.startswith("sqlite"):
        database.init_db()
    log.info(
        "LinguaCall API starting: env=%s provider=%s realtime=%s db=%s",
        settings.ENV, settings.provider, ai.realtime_available(),
        settings.DATABASE_URL.split("://", 1)[0],
    )


# ---------- helpers ----------
def get_or_create_user(db: Session, username: str) -> database.User:
    username = (username or "guest").strip().lower()
    user = db.query(database.User).filter_by(username=username).first()
    if not user:
        user = database.User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ---------- schemas ----------
class LoginIn(BaseModel):
    username: str


class RealtimeIn(BaseModel):
    username: str
    mode: str  # persona | interview
    persona_id: str | None = None
    track: str | None = "sde"
    role: str | None = "SDE"
    focus: str | None = "dsa"
    difficulty: str | None = "medium"
    company_id: str | None = None
    company_name: str | None = None
    candidate_note: str | None = None
    hints_enabled: bool = True


class ChatIn(BaseModel):
    username: str
    mode: str
    persona_id: str | None = None
    track: str | None = "sde"
    role: str | None = "SDE"
    focus: str | None = "dsa"
    difficulty: str | None = "medium"
    company_id: str | None = None
    company_name: str | None = None
    candidate_note: str | None = None
    hints_enabled: bool = True
    session_id: str | None = None
    use_resume: bool = False
    job_description: str | None = None
    history: list[dict] = []  # [{role, text}]
    message: str


class SaveConversationIn(BaseModel):
    username: str
    mode: str
    persona_id: str | None = None
    title: str | None = None
    transcript: list[dict] = []


class GradeIn(BaseModel):
    username: str
    track: str | None = "sde"
    role: str = "SDE"
    focus: str = "dsa"
    difficulty: str = "medium"
    company_id: str | None = None
    company_name: str | None = None
    transcript: list[dict] = []
    session_id: str | None = None


# ---------- misc ----------
@app.get("/api/health")
def health():
    return {
        "ok": True,
        "has_openai_key": ai.has_key(),
        "provider": settings.provider,
        "realtime_available": ai.realtime_available(),
    }


@app.get("/api/config")
def client_config():
    """Public config a web or native client needs to bootstrap."""
    return {
        "has_openai_key": ai.has_key(),
        "provider": settings.provider,
        "realtime_available": ai.realtime_available(),
        "media_service_url": settings.MEDIA_SERVICE_URL,
        "video_supported": True,
        "screenshare_supported": True,
        # Feature flags for the client to hide disabled features.
        "enabled_tracks": settings.enabled_tracks_list(),
        "persona_calls_enabled": settings.ENABLE_PERSONA_CALLS,
    }


@app.get("/api/personas")
def personas():
    # Persona/English-practice calls can be disabled via feature flag.
    if not settings.ENABLE_PERSONA_CALLS:
        return []
    return p.list_personas()


@app.get("/api/interview/focuses")
def focuses():
    return [{"id": k, "label": v} for k, v in p.INTERVIEW_FOCUS.items()]


@app.get("/api/catalog/tracks")
def catalog_tracks():
    """Interview tracks, filtered by the ENABLED_TRACKS feature flag."""
    return [t for t in catalog.list_tracks() if settings.is_track_enabled(t["id"])]


@app.get("/api/catalog/companies")
def catalog_companies():
    """Curated company/board profiles; clients may also send a free-text name."""
    return catalog.list_companies()


@app.get("/api/catalog/difficulties")
def catalog_difficulties():
    return [
        {"id": k, "label": v["label"], "question": v["question"]}
        for k, v in catalog.DIFFICULTY.items()
    ]


@app.get("/api/catalog/design-topics")
def catalog_design_topics():
    """Suggested staged-design problems (payment gateway, bank, etc.). Any
    free-text topic also works via candidate_note."""
    return catalog.DESIGN_TOPICS


@app.get("/api/catalog/hint-tiers")
def catalog_hint_tiers():
    return [
        {"tier": k, "label": v["label"], "penalty": v["penalty"], "reveal": v["reveal"]}
        for k, v in catalog.HINT_TIERS.items()
    ]


@app.post("/api/login")
def login(body: LoginIn, db: Session = Depends(database.get_db)):
    """Legacy guest login (username only). Kept for backward compatibility; new
    clients should use /api/auth/*. Returns a token too so it works uniformly."""
    user = get_or_create_user(db, body.username)
    return {"id": user.id, "username": user.username, "token": auth.create_token(user)}


# ---------- real auth (email + password) ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    username: str | None = None


class AuthLoginIn(BaseModel):
    email: EmailStr
    password: str


def _auth_response(user: database.User) -> dict:
    return {
        "token": auth.create_token(user),
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@app.post("/api/auth/register")
def auth_register(body: RegisterIn, db: Session = Depends(database.get_db)):
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


@app.post("/api/auth/login")
def auth_login(body: AuthLoginIn, db: Session = Depends(database.get_db)):
    email = body.email.lower().strip()
    user = db.query(database.User).filter_by(email=email).first()
    if not user or not user.password_hash or not auth.verify_password(
        body.password, user.password_hash
    ):
        raise HTTPException(401, "Invalid email or password.")
    return _auth_response(user)


@app.get("/api/auth/me")
def auth_me(user: database.User | None = Depends(auth.optional_user)):
    if not user:
        raise HTTPException(401, "Not authenticated.")
    return {"id": user.id, "username": user.username, "email": user.email}


# ---------- realtime ----------
def _build_instructions(db: Session, body: RealtimeIn) -> tuple[str, str]:
    if body.mode == "interview":
        instr = p.build_interview_instructions(
            body.role or "SDE",
            body.focus or "dsa",
            body.difficulty or "medium",
            track=body.track,
            company_id=body.company_id,
            company_name=body.company_name,
            candidate_note=body.candidate_note,
            hints_enabled=body.hints_enabled,
        )
        trk = catalog.resolve_track(body.track)
        return instr, trk.get("default_voice", "verse")
    # persona
    user = get_or_create_user(db, body.username)
    persona_id = body.persona_id or "emma"
    mems = (
        db.query(database.Memory)
        .filter_by(user_id=user.id, persona_id=persona_id)
        .all()
    )
    instr = p.build_persona_instructions(persona_id, [m.fact for m in mems])
    voice = p.PERSONAS.get(persona_id, p.PERSONAS["emma"])["voice"]
    return instr, voice


@app.post("/api/realtime/session")
async def realtime_session(body: RealtimeIn, db: Session = Depends(database.get_db)):
    if not ai.has_key():
        raise HTTPException(400, "LLM provider not configured on the server.")
    if not ai.realtime_available():
        raise HTTPException(
            400,
            "Realtime voice is not configured. For Azure, set "
            "AZURE_OPENAI_REALTIME_ENDPOINT and AZURE_OPENAI_REALTIME_DEPLOYMENT.",
        )
    instructions, voice = _build_instructions(db, body)
    try:
        session = await ai.create_realtime_session(instructions, voice)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Failed to create realtime session: {e}")
    return session


# ---------- text chat fallback ----------
def _live_screen_context(db: Session, session_id: str | None, focus: str | None) -> str:
    """Build a block describing what the interviewer can currently see:
    the whiteboard (design focuses) or the candidate's code + test results
    (coding focus). Empty string if nothing to show."""
    if not session_id:
        return ""
    sess = db.get(database.Session, session_id)
    if not sess:
        return ""
    parts = []
    # Design: structured architecture graph + AI's reading (gaps, last change).
    if catalog.is_staged_design(focus):
        block = vision_service.live_diagram_context(sess)
        if block:
            parts.append(block)
    # Coding: the candidate's current code + latest test outcome.
    if (focus or "") == "dsa" and sess.code_source:
        lang = sess.code_language or "their language"
        block = (
            "THE CANDIDATE'S CURRENT CODE (in "
            f"{lang}):\n```\n{sess.code_source[:4000]}\n```"
        )
        if sess.code_result:
            cr = sess.code_result
            block += (
                f"\nLatest run: examples {cr.get('example_passed')}/"
                f"{cr.get('example_total')} passed, hidden "
                f"{cr.get('hidden_passed')}/{cr.get('hidden_total')} passed."
            )
        block += (
            "\nReview their actual code: ask about time/space complexity, edge "
            "cases, and any failing tests. Point to specific lines/logic. If tests "
            "fail, probe why rather than giving the fix."
        )
        parts.append(block)
    return "\n\n".join(parts)


@app.post("/api/chat")
@limiter.limit(settings.RATE_LIMIT_LLM)
def chat(
    request: Request,
    body: ChatIn,
    db: Session = Depends(database.get_db),
    authed: database.User | None = Depends(auth.optional_user),
):
    if not ai.has_key():
        raise HTTPException(400, "OPENAI_API_KEY not configured on the server.")
    if body.mode == "interview":
        system = p.build_interview_instructions(
            body.role or "SDE",
            body.focus or "dsa",
            body.difficulty or "medium",
            track=body.track,
            company_id=body.company_id,
            company_name=body.company_name,
            candidate_note=body.candidate_note,
            hints_enabled=body.hints_enabled,
        )
        # Inject what the interviewer can currently "see": the candidate's
        # whiteboard (design) and their code + test results (coding), so it can
        # ask concrete, real follow-ups — like a human watching the screen.
        live = _live_screen_context(db, body.session_id, body.focus)
        if live:
            system += "\n\n" + live
        # Tailor to the candidate's resume + target job when requested.
        if (body.use_resume and authed and authed.resume_summary) or body.job_description:
            system += resume_mod.interview_resume_block(
                authed.resume_summary if (body.use_resume and authed) else None,
                body.job_description,
            )
        # COMPREHENSIVENESS: for design interviews, track a coverage checklist and
        # drive the interviewer toward uncovered items; refuse wrap-up with gaps.
        if catalog.is_staged_design(body.focus) and body.session_id:
            sess = db.get(database.Session, body.session_id)
            if sess:
                cov = coverage.ensure_coverage(sess)
                # Update statuses from the conversation so far (+ this message).
                full_hist = list(body.history) + [{"role": "user", "text": body.message}]
                cov = coverage.update_coverage(cov, full_hist)
                sess.coverage_state = cov
                db.commit()
                block = coverage.coverage_prompt_block(cov)
                if block:
                    system += block
    else:
        user = get_or_create_user(db, body.username)
        pid = body.persona_id or "emma"
        mems = (
            db.query(database.Memory)
            .filter_by(user_id=user.id, persona_id=pid)
            .all()
        )
        system = p.build_persona_instructions(pid, [m.fact for m in mems])
    messages = [{"role": "system", "content": system}]
    for turn in body.history:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": turn.get("text", "")})
    messages.append({"role": "user", "content": body.message})
    reply = ai.chat(messages)
    return {"reply": reply}


# ---------- persist a persona conversation + extract memories ----------
@app.post("/api/conversations")
def save_conversation(body: SaveConversationIn, db: Session = Depends(database.get_db)):
    user = get_or_create_user(db, body.username)
    result = {"summary": "", "memories": []}
    if body.mode == "persona":
        result = services.summarize_and_extract(body.transcript)
    convo = database.Conversation(
        user_id=user.id,
        mode=body.mode,
        persona_id=body.persona_id,
        title=body.title or "Conversation",
        transcript=body.transcript,
        summary=result["summary"],
    )
    db.add(convo)
    for fact in result["memories"]:
        db.add(
            database.Memory(
                user_id=user.id, persona_id=body.persona_id, fact=fact
            )
        )
    db.commit()
    db.refresh(convo)
    return {
        "id": convo.id,
        "summary": convo.summary,
        "new_memories": result["memories"],
    }


# ---------- grade an interview ----------
@app.post("/api/interview/grade")
@limiter.limit(settings.RATE_LIMIT_LLM)
def grade(
    request: Request,
    body: GradeIn,
    db: Session = Depends(database.get_db),
    authed: database.User | None = Depends(auth.optional_user),
):
    # Attribute the report to the logged-in account when available (so it shows
    # up in their progress and recordings); fall back to the guest username.
    user = authed or get_or_create_user(db, body.username)

    # Fold in visual observations captured during the session, if any.
    observations_summary = ""
    transcript = body.transcript
    track = body.track
    focus = body.focus
    difficulty = body.difficulty
    role = body.role
    company_id = body.company_id
    company_name = body.company_name
    if body.session_id:
        sess = db.get(database.Session, body.session_id)
        if sess:
            obs = [
                {"source": o.source, "note": o.note, "flags": o.flags}
                for o in sess.observations
            ]
            observations_summary = vision_service.summarize_observations(obs)
            # Include the structured final architecture for the design grader.
            diagram_summary = vision_service.summarize_for_grader(sess)
            if diagram_summary:
                observations_summary = (
                    (observations_summary + "\n\n" if observations_summary else "")
                    + diagram_summary
                )
            # Coverage map — what the interview did/didn't cover (comprehensiveness).
            cov_map = coverage.coverage_map_for_grader(sess.coverage_state or {})
            if cov_map:
                observations_summary = (
                    (observations_summary + "\n\n" if observations_summary else "")
                    + cov_map
                )
            if not transcript and sess.transcript:
                transcript = sess.transcript
            # Prefer the session's stored setup for accurate grading.
            track = sess.track or track
            focus = sess.focus or focus
            difficulty = sess.difficulty or difficulty
            role = sess.role or role
            company_id = sess.company_id or company_id
            company_name = sess.company_name or company_name
            # Persist the final transcript on the session for replay.
            if transcript:
                sess.transcript = transcript
            sess.status = "ended"
            sess.ended_at = datetime.utcnow()

    # Collect hints used in this session so scoring can honestly penalize them.
    hints_list = []
    code_summary = ""
    if body.session_id:
        for h in db.query(database.Hint).filter_by(session_id=body.session_id).all():
            hints_list.append(
                {"tier": h.tier, "penalty": h.penalty,
                 "label": catalog.HINT_TIERS.get(h.tier, {}).get("label", "")}
            )
        sess2 = db.get(database.Session, body.session_id)
        if sess2 and sess2.code_result:
            cr = sess2.code_result
            code_summary = (
                f"language={sess2.code_language}; "
                f"example tests {cr.get('example_passed')}/{cr.get('example_total')} passed, "
                f"hidden tests {cr.get('hidden_passed')}/{cr.get('hidden_total')} passed."
            )

    company = catalog.resolve_company(company_id, company_name)
    report = services.grade_interview(
        role, focus, difficulty, transcript, observations_summary,
        track=track, company_id=company_id, company_name=company_name,
        hints=hints_list, code_summary=code_summary,
    )
    row = database.InterviewReport(
        user_id=user.id,
        session_id=body.session_id,
        role=role,
        track=track,
        focus=focus,
        difficulty=difficulty,
        company=company["name"],
        overall_score=report["overall_score"],
        hints_used=report.get("hints_used", 0),
        hint_penalty=report.get("hint_penalty", 0),
        scores=report["scores"],
        strengths=report["strengths"],
        improvements=report["improvements"],
        rubric=report.get("rubric", []),
        feedback=report["feedback"],
    )
    db.add(row)
    # also persist the transcript
    db.add(
        database.Conversation(
            user_id=user.id,
            mode="interview",
            title=f"{company['name']} · {role} · {focus} interview",
            transcript=transcript,
            summary=report["feedback"][:400],
        )
    )
    db.commit()
    db.refresh(row)
    return {"id": row.id, **report}


class CoachingIn(BaseModel):
    role: str = "SDE"
    track: str | None = "sde"
    focus: str = "dsa"
    difficulty: str = "medium"
    transcript: list[dict] = []
    report: dict | None = None
    session_id: str | None = None


@app.post("/api/interview/coaching")
@limiter.limit(settings.RATE_LIMIT_LLM)
def coaching(request: Request, body: CoachingIn, db: Session = Depends(database.get_db)):
    """Post-interview coaching: model answers for weak questions, key concepts to
    study, and a recommended next drill. Generated on demand."""
    transcript = body.transcript
    track, focus, difficulty, role = body.track, body.focus, body.difficulty, body.role
    if body.session_id:
        sess = db.get(database.Session, body.session_id)
        if sess:
            if not transcript and sess.transcript:
                transcript = sess.transcript
            track = sess.track or track
            focus = sess.focus or focus
            difficulty = sess.difficulty or difficulty
            role = sess.role or role
    return services.generate_coaching(
        role, focus, difficulty, transcript, report=body.report, track=track
    )


# ---------- dashboard / history ----------
@app.get("/api/stats")
def stats(
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    """Personal progress analytics: trends, weak areas, streaks. Requires login."""
    if not user:
        raise HTTPException(401, "Log in to see your progress.")
    return analytics.compute_stats(db, user.id)


@app.get("/api/leaderboard")
def leaderboard_endpoint(
    track: str | None = None,
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    """Global or per-track leaderboard by best score. Everyone auto-listed."""
    return lb.leaderboard(db, track=track, me_id=user.id if user else None)


@app.get("/api/challenge")
def challenge_endpoint(
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    """This week's shared challenge + its leaderboard."""
    return lb.challenge_leaderboard(db, me_id=user.id if user else None)


# ---------- curriculum: company packs, learning paths, spaced repetition ----------
@app.get("/api/company-packs")
def company_packs():
    return curriculum.list_company_packs()


@app.get("/api/learning-paths")
def learning_paths(
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    paths = curriculum.list_learning_paths()
    if user:
        return [curriculum.path_progress(db, user.id, p) for p in paths]
    return [{**p, "completed": 0, "total": len(p["steps"])} for p in paths]


@app.get("/api/review-queue")
def review_queue(
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    """Spaced-repetition: concepts the user should review, from past weak areas."""
    if not user:
        raise HTTPException(401, "Log in to see your review queue.")
    return curriculum.review_queue(db, user.id)


@app.get("/api/replay/{report_id}")
def replay(
    report_id: int,
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    """Full recording of a past interview: report + transcript + code + diagram."""
    if not user:
        raise HTTPException(401, "Log in to view recordings.")
    rep = db.get(database.InterviewReport, report_id)
    if not rep or rep.user_id != user.id:
        raise HTTPException(404, "Recording not found.")
    sess = db.get(database.Session, rep.session_id) if rep.session_id else None
    return {
        "report": {
            "id": rep.id, "role": rep.role, "track": rep.track, "focus": rep.focus,
            "difficulty": rep.difficulty, "company": rep.company,
            "overall_score": rep.overall_score, "scores": rep.scores,
            "strengths": rep.strengths, "improvements": rep.improvements,
            "feedback": rep.feedback, "hints_used": rep.hints_used,
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


# ---------- resume-driven interviews ----------
@app.post("/api/resume/upload")
async def resume_upload(
    file: UploadFile = File(...),
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    if not user:
        raise HTTPException(401, "Log in to upload your resume.")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Resume too large (max 5MB).")
    text = resume_mod.extract_text(file.filename or "", data)
    if not text.strip():
        raise HTTPException(400, "Could not read any text from that file. Try a PDF or DOCX.")
    summary = resume_mod.summarize(text)
    user.resume_text = text[:20000]
    user.resume_summary = summary
    db.commit()
    return {"summary": summary, "chars": len(text)}


@app.get("/api/resume")
def resume_get(user: database.User | None = Depends(auth.optional_user)):
    if not user:
        raise HTTPException(401, "Log in to view your resume.")
    return {
        "has_resume": bool(user.resume_summary),
        "summary": user.resume_summary or "",
    }


@app.delete("/api/resume")
def resume_clear(
    user: database.User | None = Depends(auth.optional_user),
    db: Session = Depends(database.get_db),
):
    if not user:
        raise HTTPException(401, "Log in first.")
    user.resume_text = None
    user.resume_summary = None
    db.commit()
    return {"ok": True}


@app.get("/api/history/{username}")
def history(username: str, db: Session = Depends(database.get_db)):
    user = get_or_create_user(db, username)
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
        "memories": [
            {"id": m.id, "persona_id": m.persona_id, "fact": m.fact}
            for m in mems
        ],
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
