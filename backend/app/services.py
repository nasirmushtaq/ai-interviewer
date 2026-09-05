"""Post-call processing: summarize a transcript and extract durable memories,
and grade interviews."""

from . import catalog
from . import openai_service as ai


def _transcript_text(transcript: list[dict]) -> str:
    lines = []
    for turn in transcript:
        role = turn.get("role", "user")
        speaker = "Learner" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.get('text', '')}")
    return "\n".join(lines)


def summarize_and_extract(transcript: list[dict]) -> dict:
    """Returns {summary, memories: [str]} for a persona conversation."""
    if not transcript:
        return {"summary": "", "memories": []}
    if not ai.has_key():
        return {"summary": "(summary unavailable — no API key)", "memories": []}

    convo = _transcript_text(transcript)
    messages = [
        {
            "role": "system",
            "content": (
                "You process an English-practice call transcript. Return JSON with "
                "keys: 'summary' (2-3 sentence recap) and 'memories' (a list of "
                "short durable facts worth remembering about the LEARNER for future "
                "calls — interests, goals, job, name, level, etc). Only include "
                "genuinely useful, stable facts. Empty list if none."
            ),
        },
        {"role": "user", "content": convo},
    ]
    try:
        data = ai.chat_json(messages)
    except Exception as e:
        return {"summary": f"(summary failed: {e})", "memories": []}
    mems = data.get("memories") or []
    mems = [str(m).strip() for m in mems if str(m).strip()]
    return {"summary": data.get("summary", ""), "memories": mems}


GRADING_SYSTEM = (
    "You are a senior engineering interviewer grading a completed technical "
    "interview transcript. Be fair but rigorous, like a real FAANG interviewer. "
    "Return JSON with keys: "
    "'overall_score' (int 0-100), "
    "'scores' (object with int 0-100 for keys: problem_solving, technical_depth, "
    "communication, correctness), "
    "'strengths' (list of short strings), "
    "'improvements' (list of short actionable strings), "
    "'feedback' (a detailed 1-2 paragraph written assessment addressed to the "
    "candidate, with a hiring signal like 'lean hire' / 'no hire')."
)

# Full system-design rubric with TEACHING feedback (what was weak AND how a
# strong candidate reasons about it).
DESIGN_GRADING_SYSTEM = (
    "You are a world-class system design interviewer writing a detailed, teaching "
    "evaluation of a completed interview. Consider the transcript AND the "
    "candidate's whiteboard architecture. Be rigorous and specific — reference "
    "actual components and answers.\n\n"
    "Return STRICT JSON with keys:\n"
    "'overall_score' (int 0-100),\n"
    "'scores' (object, int 0-100, keys: requirements, estimation, api_data_model, "
    "high_level_architecture, data_flow, storage_consistency, caching_performance, "
    "availability_fault_tolerance, scalability_partitioning, "
    "concurrency_distributed, security_reliability, operations, tradeoffs, "
    "communication),\n"
    "'rubric' (list of objects, ONE per weak or notable area, each "
    "{area, score, what_happened, how_a_strong_candidate_reasons} — the last field "
    "TEACHES: explain concretely how a strong candidate would have reasoned about "
    "that area, with specifics),\n"
    "'strengths' (list of short strings),\n"
    "'improvements' (list of short actionable strings),\n"
    "'feedback' (2-3 paragraph written assessment addressed to the candidate, with "
    "a hiring signal like 'strong hire' / 'lean hire' / 'no hire'). Make the whole "
    "evaluation feel like an exceptional learning experience."
)


def generate_hint(
    tier: int,
    reveal: str,
    question_context: str,
    transcript: list[dict],
    role: str,
    focus: str,
    track: str | None = None,
) -> str:
    """Produce a single tiered hint for the candidate's current question."""
    if not ai.has_key():
        return "(hint unavailable — no API key configured)"
    trk = catalog.resolve_track(track or "sde")
    _, focus_brief = catalog.resolve_focus(trk, focus)
    convo = _transcript_text(transcript[-8:]) if transcript else ""
    system = (
        "You are the interviewer's hint generator. Give ONE hint at the requested "
        f"level: {reveal}. Keep it to 1-3 sentences, encouraging and specific to the "
        "candidate's current question and where they are. Never exceed the requested "
        "reveal level, and never give the complete final solution."
    )
    user = (
        f"Track/focus: {trk['name']} — {focus_brief}\n"
        f"Current question / context: {question_context or '(infer from transcript)'}\n"
        f"Recent transcript:\n{convo}\n\nGive the hint now."
    )
    try:
        return ai.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.5,
        ).strip()
    except Exception as e:
        return f"(hint failed: {e})"


def grade_interview(
    role: str,
    focus: str,
    difficulty: str,
    transcript: list[dict],
    observations_summary: str = "",
    track: str | None = None,
    company_id: str | None = None,
    company_name: str | None = None,
    hints: list[dict] | None = None,
    code_summary: str = "",
) -> dict:
    if not ai.has_key():
        return {
            "overall_score": 0,
            "scores": {},
            "strengths": [],
            "improvements": ["Add an OpenAI API key to enable grading."],
            "feedback": "Grading unavailable — no API key configured.",
            "hints_used": len(hints or []),
            "hint_penalty": sum(h.get("penalty", 0) for h in (hints or [])),
        }
    trk = catalog.resolve_track(
        track or ("sde" if focus in catalog.TRACKS["sde"]["focuses"] else "generic")
    )
    _, focus_brief = catalog.resolve_focus(trk, focus)
    company = catalog.resolve_company(company_id, company_name)
    diff = catalog.resolve_difficulty(difficulty)

    convo = _transcript_text(transcript)
    vision_block = (
        f"\n\n{observations_summary}\n\nUse these visual observations as supporting "
        "signal for communication/engagement and to note any integrity concerns, "
        "but grade primarily on the substance of the answers."
        if observations_summary
        else ""
    )
    hints = hints or []
    hint_penalty = sum(int(h.get("penalty", 0)) for h in hints)
    hints_block = ""
    if hints:
        tiers = ", ".join(f"tier {h.get('tier')} ({h.get('label','')})" for h in hints)
        hints_block = (
            f"\n\nThe candidate requested {len(hints)} hint(s) during the interview "
            f"[{tiers}]. Note in your feedback where they needed help; the raw score "
            "will be penalized automatically, so grade the answers on their merits and "
            "do not double-penalize."
        )
    context = (
        f"Interview context:\n"
        f"- Role: {role or trk['name']}\n"
        f"- Track: {trk['name']} — {focus_brief}\n"
        f"- Company/board: {company['name']} ({company['style']})\n"
        f"- Difficulty: {diff['label']}. Grading calibration: {diff['grading']}. "
        f"A strong 'hire' at this level roughly clears {diff['bar']}/100.\n"
    )
    code_block = (
        f"\n\nCoding result — {code_summary}\n"
        "Weight actual test outcomes heavily for correctness; a solution that fails "
        "hidden tests should not score as fully correct even if the discussion was good."
        if code_summary
        else ""
    )
    is_design = catalog.is_staged_design(focus)
    grading_prompt = DESIGN_GRADING_SYSTEM if is_design else GRADING_SYSTEM
    messages = [
        {"role": "system", "content": grading_prompt},
        {
            "role": "user",
            "content": f"{context}\nTranscript:\n{convo}{vision_block}{hints_block}{code_block}",
        },
    ]
    try:
        data = ai.chat_json(messages)
    except Exception as e:
        return {
            "overall_score": 0,
            "scores": {},
            "strengths": [],
            "improvements": [],
            "feedback": f"Grading failed: {e}",
            "hints_used": len(hints),
            "hint_penalty": hint_penalty,
        }
    raw = int(data.get("overall_score", 0))
    final = max(0, raw - hint_penalty)
    return {
        "overall_score": final,
        "raw_score": raw,
        "hints_used": len(hints),
        "hint_penalty": hint_penalty,
        "scores": data.get("scores", {}),
        "rubric": data.get("rubric", []),
        "strengths": data.get("strengths", []),
        "improvements": data.get("improvements", []),
        "feedback": data.get("feedback", ""),
    }


COACHING_SYSTEM = (
    "You are an interview coach reviewing a candidate's completed mock interview. "
    "Produce concise, actionable coaching. Return STRICT JSON with keys: "
    "'model_answers' (a list of up to 3 objects {question, what_you_missed, "
    "strong_answer} — pick the questions where the candidate was weakest; "
    "'strong_answer' is a crisp outline of how a strong candidate would answer, "
    "not an essay), "
    "'key_concepts' (list of specific concepts/topics the candidate should study, "
    "e.g. 'consistent hashing', 'cache invalidation', 'DB indexing'), "
    "'next_drill' (an object {focus, difficulty, reason} recommending the single "
    "most valuable next practice session — focus must be a short slug like "
    "'system_design' or 'dsa'), "
    "'action_plan' (list of 3-5 short concrete steps to improve)."
)


def generate_coaching(
    role: str,
    focus: str,
    difficulty: str,
    transcript: list[dict],
    report: dict | None = None,
    track: str | None = None,
) -> dict:
    if not ai.has_key():
        return {
            "model_answers": [],
            "key_concepts": [],
            "next_drill": None,
            "action_plan": ["Add an OpenAI API key to enable coaching."],
        }
    convo = _transcript_text(transcript)
    rep = ""
    if report:
        rep = (
            f"\n\nGrader summary — overall {report.get('overall_score')}, "
            f"per-dimension {report.get('scores')}, "
            f"improvements {report.get('improvements')}."
        )
    messages = [
        {"role": "system", "content": COACHING_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Role: {role}\nTrack: {track}\nFocus: {focus}\n"
                f"Difficulty: {difficulty}\n\nTranscript:\n{convo}{rep}"
            ),
        },
    ]
    try:
        data = ai.chat_json(messages)
    except Exception as e:
        return {
            "model_answers": [],
            "key_concepts": [],
            "next_drill": None,
            "action_plan": [f"Coaching failed: {e}"],
        }
    return {
        "model_answers": data.get("model_answers", []),
        "key_concepts": data.get("key_concepts", []),
        "next_drill": data.get("next_drill"),
        "action_plan": data.get("action_plan", []),
    }
