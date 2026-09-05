"""Interview orchestration: the business logic that used to live inside the
``/api/chat``, ``/api/interview/*`` and ``/api/realtime/session`` handlers.

This layer knows about prompts, coverage tracking, the LLM client and the DB,
but nothing about HTTP. It raises :mod:`app.errors` exceptions instead of
``HTTPException`` so it can be reused (jobs, tests, other transports) unchanged.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from . import catalog, coverage, services, vision_service
from . import db as database
from . import openai_service as ai
from . import personas as p
from . import resume as resume_mod
from .dependencies import get_or_create_user
from .errors import NotConfiguredError, UpstreamError
from .schemas import ChatIn, CoachingIn, GradeIn, RealtimeIn


# --------------------------------------------------------------------------- #
# Prompt assembly helpers
# --------------------------------------------------------------------------- #
def build_instructions(db: Session, body: RealtimeIn) -> tuple[str, str]:
    """Return the (system instructions, voice) for a realtime session."""
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
    mems = db.query(database.Memory).filter_by(user_id=user.id, persona_id=persona_id).all()
    instr = p.build_persona_instructions(persona_id, [m.fact for m in mems])
    voice = p.PERSONAS.get(persona_id, p.PERSONAS["emma"])["voice"]
    return instr, voice


def _live_screen_context(db: Session, session_id: str | None, focus: str | None) -> str:
    """Describe what the interviewer can currently "see": the whiteboard (design
    focuses) or the candidate's code + test results (coding focus). Empty string
    if there is nothing to show."""
    if not session_id:
        return ""
    sess = db.get(database.Session, session_id)
    if not sess:
        return ""
    parts: list[str] = []
    # Design: structured architecture graph + AI's reading (gaps, last change).
    if catalog.is_staged_design(focus):
        block = vision_service.live_diagram_context(sess)
        if block:
            parts.append(block)
    # Coding: the candidate's current code + latest test outcome.
    if (focus or "") == "dsa" and sess.code_source:
        lang = sess.code_language or "their language"
        block = "THE CANDIDATE'S CURRENT CODE (in " f"{lang}):\n```\n{sess.code_source[:4000]}\n```"
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


def _build_chat_system_prompt(db: Session, body: ChatIn, authed: database.User | None) -> str:
    """Assemble the full system prompt for a text-chat turn (interview or persona)."""
    if body.mode != "interview":
        user = get_or_create_user(db, body.username)
        pid = body.persona_id or "emma"
        mems = db.query(database.Memory).filter_by(user_id=user.id, persona_id=pid).all()
        return p.build_persona_instructions(pid, [m.fact for m in mems])

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
    # Inject what the interviewer can currently "see": the candidate's whiteboard
    # (design) and their code + test results (coding), so it can ask concrete,
    # real follow-ups — like a human watching the screen.
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
            full_hist = [*body.history, {"role": "user", "text": body.message}]
            cov = coverage.update_coverage(cov, full_hist)
            sess.coverage_state = cov
            db.commit()
            block = coverage.coverage_prompt_block(cov)
            if block:
                system += block
    return system


# --------------------------------------------------------------------------- #
# Public service operations
# --------------------------------------------------------------------------- #
async def create_realtime_session(db: Session, body: RealtimeIn) -> dict:
    if not ai.has_key():
        raise NotConfiguredError("LLM provider not configured on the server.")
    if not ai.realtime_available():
        raise NotConfiguredError(
            "Realtime voice is not configured. For Azure, set "
            "AZURE_OPENAI_REALTIME_ENDPOINT and AZURE_OPENAI_REALTIME_DEPLOYMENT."
        )
    instructions, voice = build_instructions(db, body)
    try:
        return await ai.create_realtime_session(instructions, voice)
    except Exception as e:
        raise UpstreamError(f"Failed to create realtime session: {e}")


def generate_chat_reply(db: Session, body: ChatIn, authed: database.User | None) -> str:
    if not ai.has_key():
        raise NotConfiguredError("OPENAI_API_KEY not configured on the server.")
    system = _build_chat_system_prompt(db, body, authed)
    messages = [{"role": "system", "content": system}]
    for turn in body.history:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": turn.get("text", "")})
    messages.append({"role": "user", "content": body.message})
    return ai.chat(messages)


def _session_grading_context(db: Session, body: GradeIn) -> tuple[dict, list[dict], str]:
    """Gather everything the grader needs from a persisted session: folded-in
    visual observations, the effective interview setup, the hint list and a code
    summary. Returns (overrides, hints, code_summary) where ``overrides`` carries
    the resolved transcript/track/focus/etc. Also finalises the session row."""
    overrides: dict = {
        "transcript": body.transcript,
        "track": body.track,
        "focus": body.focus,
        "difficulty": body.difficulty,
        "role": body.role,
        "company_id": body.company_id,
        "company_name": body.company_name,
        "observations_summary": "",
    }
    hints_list: list[dict] = []
    code_summary = ""
    if not body.session_id:
        return overrides, hints_list, code_summary

    sess = db.get(database.Session, body.session_id)
    if sess:
        obs = [{"source": o.source, "note": o.note, "flags": o.flags} for o in sess.observations]
        summary = vision_service.summarize_observations(obs)
        # Include the structured final architecture for the design grader.
        diagram_summary = vision_service.summarize_for_grader(sess)
        if diagram_summary:
            summary = (summary + "\n\n" if summary else "") + diagram_summary
        # Coverage map — what the interview did/didn't cover (comprehensiveness).
        cov_map = coverage.coverage_map_for_grader(sess.coverage_state or {})
        if cov_map:
            summary = (summary + "\n\n" if summary else "") + cov_map
        overrides["observations_summary"] = summary

        if not overrides["transcript"] and sess.transcript:
            overrides["transcript"] = sess.transcript
        # Prefer the session's stored setup for accurate grading.
        overrides["track"] = sess.track or overrides["track"]
        overrides["focus"] = sess.focus or overrides["focus"]
        overrides["difficulty"] = sess.difficulty or overrides["difficulty"]
        overrides["role"] = sess.role or overrides["role"]
        overrides["company_id"] = sess.company_id or overrides["company_id"]
        overrides["company_name"] = sess.company_name or overrides["company_name"]
        # Persist the final transcript on the session for replay.
        if overrides["transcript"]:
            sess.transcript = overrides["transcript"]
        sess.status = "ended"
        sess.ended_at = datetime.utcnow()

    # Collect hints used in this session so scoring can honestly penalize them.
    for h in db.query(database.Hint).filter_by(session_id=body.session_id).all():
        hints_list.append(
            {
                "tier": h.tier,
                "penalty": h.penalty,
                "label": catalog.HINT_TIERS.get(h.tier, {}).get("label", ""),
            }
        )
    if sess and sess.code_result:
        cr = sess.code_result
        code_summary = (
            f"language={sess.code_language}; "
            f"example tests {cr.get('example_passed')}/{cr.get('example_total')} passed, "
            f"hidden tests {cr.get('hidden_passed')}/{cr.get('hidden_total')} passed."
        )
    return overrides, hints_list, code_summary


def grade_session(db: Session, body: GradeIn, authed: database.User | None) -> dict:
    # Attribute the report to the logged-in account when available (so it shows
    # up in their progress and recordings); fall back to the guest username.
    user = authed or get_or_create_user(db, body.username)

    overrides, hints_list, code_summary = _session_grading_context(db, body)
    transcript = overrides["transcript"]
    track = overrides["track"]
    focus = overrides["focus"]
    difficulty = overrides["difficulty"]
    role = overrides["role"]
    company_id = overrides["company_id"]
    company_name = overrides["company_name"]

    company = catalog.resolve_company(company_id, company_name)
    report = services.grade_interview(
        role,
        focus,
        difficulty,
        transcript,
        overrides["observations_summary"],
        track=track,
        company_id=company_id,
        company_name=company_name,
        hints=hints_list,
        code_summary=code_summary,
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
    # Also persist the transcript as a conversation for history/replay.
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


def generate_coaching(db: Session, body: CoachingIn) -> dict:
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


def save_conversation(db: Session, body, user: database.User) -> dict:
    """Persist a (persona) conversation and extract long-term memories from it."""
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
        db.add(database.Memory(user_id=user.id, persona_id=body.persona_id, fact=fact))
    db.commit()
    db.refresh(convo)
    return {"id": convo.id, "summary": convo.summary, "new_memories": result["memories"]}
