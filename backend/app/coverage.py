"""Coverage engine: keeps a live checklist of what the interview has covered,
updating item statuses from the conversation, so the interviewer can guarantee a
comprehensive interview (never wraps up with gaps)."""

import json

from . import checklists
from . import openai_service as ai


def ensure_coverage(session) -> dict:
    """Get (or lazily create) the coverage state for a session, detecting the
    concrete topic from the opening/first messages."""
    cov = getattr(session, "coverage_state", None)
    if cov and cov.get("items"):
        return cov
    # Detect topic from transcript + candidate_note if available.
    text = ""
    for t in (session.transcript or [])[:4]:
        text += " " + (t.get("text") or "")
    topic = checklists.detect_topic(text)
    return checklists.init_coverage(topic)


_UPDATE_SYSTEM = (
    "You maintain a coverage checklist for a system-design interview. Given the "
    "current checklist (each item with a status) and the recent conversation, "
    "update each item's status based ONLY on what has actually been discussed:\n"
    "- 'not_asked': the interviewer has not yet raised this and the candidate "
    "hasn't addressed it.\n"
    "- 'asked': it was raised but not adequately answered yet.\n"
    "- 'answered_weak': the candidate addressed it but poorly / superficially.\n"
    "- 'answered_strong': the candidate addressed it well.\n"
    "Be strict: only mark answered_strong when the candidate genuinely covered it "
    'with substance. Return STRICT JSON: {"items": [{"item": str, "status": '
    "str}, ...]} echoing every item with its updated status."
)


def update_coverage(coverage: dict, transcript: list[dict]) -> dict:
    """Update item statuses from the conversation. Falls back to the existing
    state if the model call fails."""
    if not ai.has_key() or not coverage.get("items"):
        return coverage
    convo = "\n".join(f"{t.get('role')}: {t.get('text','')}" for t in (transcript or [])[-16:])
    checklist_text = json.dumps(
        [{"item": i["item"], "status": i["status"]} for i in coverage["items"]]
    )
    try:
        data = ai.chat_json(
            [
                {"role": "system", "content": _UPDATE_SYSTEM},
                {
                    "role": "user",
                    "content": f"Checklist:\n{checklist_text}\n\nConversation:\n{convo}\n\n"
                    "Return the updated items JSON.",
                },
            ]
        )
    except Exception:
        return coverage
    # Merge returned statuses back by item text.
    status_by_item = {str(x.get("item")): str(x.get("status")) for x in (data.get("items") or [])}
    valid = {"not_asked", "asked", "answered_weak", "answered_strong"}
    for i in coverage["items"]:
        s = status_by_item.get(i["item"])
        if s in valid:
            i["status"] = s
    return coverage


def coverage_prompt_block(coverage: dict) -> str:
    """Inject the coverage state + the next targets into the interviewer prompt so
    the model attacks uncovered items and refuses to wrap up with gaps."""
    if not coverage.get("items"):
        return ""
    summary = checklists.coverage_summary(coverage)
    targets = checklists.next_targets(coverage, n=3)
    complete = summary["complete"]

    lines = [
        "\n\nINTERVIEW COVERAGE STATE (you MUST use this to stay comprehensive):",
        f"Progress: {summary['answered_strong']} strong / "
        f"{summary['answered_weak']} weak / {summary['asked']} asked / "
        f"{summary['not_asked']} not-yet-asked, out of {summary['total']} "
        "mandatory items.",
    ]
    if targets:
        lines.append(
            "NEXT, you must drive toward these uncovered/weak items "
            "(pick the most natural one and ask about it specifically):"
        )
        for t in targets:
            lines.append(f"  - [{t['area']}] {t['item']} (status: {t['status']})")
    if not complete:
        lines.append(
            "The interview is NOT complete — there are still mandatory items not yet "
            "asked. DO NOT wrap up, summarize, or conclude the interview. Keep "
            "asking, one focused question at a time, until every item has at least "
            "been asked. If the candidate tries to wrap up, tell them there's more "
            "ground to cover and continue."
        )
    else:
        lines.append(
            "All mandatory items have been asked. You may now probe remaining weak "
            "areas or, if the candidate has answered well, move toward wrap-up."
        )
    return "\n".join(lines)


def coverage_map_for_grader(coverage: dict) -> str:
    if not coverage.get("items"):
        return ""
    by_status = {"answered_strong": [], "answered_weak": [], "asked": [], "not_asked": []}
    for i in coverage["items"]:
        by_status.setdefault(i["status"], []).append(i["item"])
    parts = ["Interview coverage map:"]
    for label, key in [
        ("Covered well", "answered_strong"),
        ("Covered weakly", "answered_weak"),
        ("Asked but unresolved", "asked"),
        ("NOT covered", "not_asked"),
    ]:
        if by_status.get(key):
            parts.append(f"- {label}: " + "; ".join(by_status[key]))
    return "\n".join(parts)
