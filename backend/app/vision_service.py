"""The AI interviewer's 'eyes' on the candidate's whiteboard.

We combine a STRUCTURED graph extracted from Excalidraw (components + directed
edges) with the rendered image, and produce a structured architectural reading:
what the design is, its data flows, and — most importantly — concrete gaps and
risks (SPOFs, missing failure handling, unvalidated scale, weak trade-offs) the
interviewer should probe. We also diff successive graphs so the interviewer can
react to specific changes the candidate makes.
"""

from . import openai_service as ai


def diagram_to_text(model: dict | None) -> str:
    """Compact text form of the structured graph for prompts."""
    if not model or not model.get("components"):
        return "(empty diagram)"
    comps = ", ".join(c.get("label", "?") for c in model["components"])
    edges = "; ".join(
        f"{e.get('from','?')} → {e.get('to','?')}" + (f" [{e['label']}]" if e.get("label") else "")
        for e in model.get("edges", [])
    )
    loose = model.get("loose_labels") or []
    loose_s = f" | notes: {', '.join(loose)}" if loose else ""
    return f"Components: {comps}\nConnections: {edges or '(none)'}{loose_s}"


ARCH_SYSTEM = (
    "You are the visual/architectural perception module for a world-class system "
    "design interviewer. You are given (a) a STRUCTURED graph of the candidate's "
    "whiteboard (components and directed connections, extracted precisely from the "
    "drawing tool) and (b) the rendered image. Trust the structured graph for what "
    "exists and how things connect; use the image to resolve ambiguity.\n\n"
    "Return STRICT JSON with keys:\n"
    "'summary' (2-3 sentences: what system this appears to be and the current shape "
    "of the architecture),\n"
    "'components' (list of short strings — the key components you see),\n"
    "'data_flows' (list of short strings describing request/data flow, e.g. "
    "'client → API gateway → order service → Postgres'),\n"
    "'gaps' (list of concrete WEAKNESSES/RISKS worth probing, each a short string — "
    "e.g. 'all writes funnel through OrderService (single bottleneck)', 'no "
    "replication on the primary DB (SPOF)', 'queue present but no dead-letter / "
    "consumer-down handling', 'cache added with no invalidation strategy', "
    "'claims millions of users but no capacity estimate', 'Cassandra chosen with no "
    "stated access pattern'),\n"
    "'flags' (list from: 'blank','no_database','no_cache','single_point_of_failure',"
    "'missing_load_balancer','unclear_connections','no_queue','no_replication'; "
    "empty if none).\n"
    "Be specific and reference actual component names from the graph. Do NOT invent "
    "components that aren't present."
)


def analyze_architecture(image_data_url: str, structure: dict | None, hint: str = "") -> dict:
    """Structured architectural reading of the current diagram."""
    if not ai.has_key():
        return {
            "summary": "(vision unavailable — no API key)",
            "components": [],
            "data_flows": [],
            "gaps": [],
            "flags": [],
        }
    graph_text = diagram_to_text(structure)
    user_text = (
        "STRUCTURED GRAPH (authoritative for existence & connections):\n"
        f"{graph_text}\n\n"
        "Now analyze the architecture. " + (f"Context: {hint}" if hint else "")
    )
    data = None
    # Prefer vision (image + graph); if the image is missing/invalid, fall back
    # to analyzing the structured graph alone (still highly useful).
    if image_data_url:
        try:
            data = ai.vision_json(ARCH_SYSTEM, user_text, [image_data_url])
        except Exception:
            data = None
    if data is None:
        try:
            data = ai.chat_json(
                [
                    {"role": "system", "content": ARCH_SYSTEM},
                    {"role": "user", "content": user_text},
                ]
            )
        except Exception as e:
            return {
                "summary": f"(analysis failed: {e})",
                "components": [],
                "data_flows": [],
                "gaps": [],
                "flags": [],
            }
    return {
        "summary": str(data.get("summary", "")).strip(),
        "components": [str(c) for c in (data.get("components") or [])],
        "data_flows": [str(f) for f in (data.get("data_flows") or [])],
        "gaps": [str(g) for g in (data.get("gaps") or [])],
        "flags": [str(f) for f in (data.get("flags") or []) if str(f).strip()],
    }


# --------------------------------------------------------------------------- #
# Structured diff — what changed between two diagram graphs.
# --------------------------------------------------------------------------- #
def _edge_key(e: dict) -> str:
    return f"{e.get('from','?')}->{e.get('to','?')}"


def diff_models(prev: dict | None, curr: dict | None) -> dict:
    """Return added/removed components & edges between two structured graphs."""
    pc = {c.get("label", "?") for c in (prev or {}).get("components", [])}
    cc = {c.get("label", "?") for c in (curr or {}).get("components", [])}
    pe = {_edge_key(e) for e in (prev or {}).get("edges", [])}
    ce = {_edge_key(e) for e in (curr or {}).get("edges", [])}
    return {
        "added_components": sorted(cc - pc),
        "removed_components": sorted(pc - cc),
        "added_connections": sorted(ce - pe),
        "removed_connections": sorted(pe - ce),
    }


def diff_to_text(diff: dict) -> str:
    parts = []
    if diff.get("added_components"):
        parts.append("added components: " + ", ".join(diff["added_components"]))
    if diff.get("removed_components"):
        parts.append("removed components: " + ", ".join(diff["removed_components"]))
    if diff.get("added_connections"):
        parts.append("new connections: " + ", ".join(diff["added_connections"]))
    if diff.get("removed_connections"):
        parts.append("removed connections: " + ", ".join(diff["removed_connections"]))
    return "; ".join(parts)


def has_changes(diff: dict) -> bool:
    return any(
        diff.get(k)
        for k in (
            "added_components",
            "removed_components",
            "added_connections",
            "removed_connections",
        )
    )


# --------------------------------------------------------------------------- #
# Proactive reaction: decide whether a diagram change warrants the interviewer
# speaking up right now, and if so, produce ONE short, specific interjection.
# Silent by default — most edits should NOT trigger a reply.
# --------------------------------------------------------------------------- #
_REACT_SYSTEM = (
    "You are a world-class system-design interviewer watching the candidate's "
    "whiteboard. The candidate JUST changed the diagram. Decide whether this "
    "change genuinely warrants you speaking up RIGHT NOW, or whether you should "
    "stay silent and let them keep working.\n"
    "React (speak) ONLY when the change is significant and a targeted follow-up "
    "adds real value — e.g. they added a component that introduces a bottleneck, "
    "SPOF, consistency issue, or a questionable choice; or removed something "
    "important; or the change contradicts an earlier decision. Do NOT react to "
    "minor/cosmetic edits, incomplete/mid-draw changes, renames, or repositioning.\n"
    "Prefer silence: when in doubt, do not interrupt. Interrupt at most occasionally.\n"
    'Return STRICT JSON: {"react": bool, "reason": string, "message": string}. '
    "'message' is what you'd say (one concise, specific question grounded in the "
    "actual component names) and is only used when react is true."
)


def decide_reaction(
    diff: dict, model: dict | None, analysis: dict | None, recent_transcript: str = ""
) -> dict:
    """Ask the model whether to proactively interject about a diagram change."""
    if not has_changes(diff) or not ai.has_key():
        return {"react": False, "reason": "no significant change", "message": ""}
    change = diff_to_text(diff)
    graph = diagram_to_text(model)
    gaps = "; ".join((analysis or {}).get("gaps", [])[:5])
    user = (
        f"Change just made: {change}\n"
        f"Current diagram: {graph}\n"
        f"Known weaknesses: {gaps or '(none noted)'}\n"
        f"Recent conversation:\n{recent_transcript or '(none)'}\n\n"
        "Should you speak up now? Return the JSON."
    )
    try:
        data = ai.chat_json(
            [
                {"role": "system", "content": _REACT_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
    except Exception:
        return {"react": False, "reason": "decision failed", "message": ""}
    return {
        "react": bool(data.get("react")),
        "reason": str(data.get("reason", "")),
        "message": str(data.get("message", "")).strip(),
    }


# --------------------------------------------------------------------------- #
# Prompt fragments consumed by the live interviewer + grader.
# --------------------------------------------------------------------------- #
def live_diagram_context(session) -> str:
    """What the interviewer can 'see' right now: the structured graph + the AI's
    architectural reading (gaps to probe) + the most recent change."""
    model = getattr(session, "diagram_model", None)
    analysis = getattr(session, "diagram_analysis", None)
    if not model and not analysis:
        return ""
    lines = ["WHAT YOU CAN SEE ON THE CANDIDATE'S WHITEBOARD RIGHT NOW:"]
    if model:
        lines.append(diagram_to_text(model))
    if analysis:
        if analysis.get("data_flows"):
            lines.append("Data flows: " + "; ".join(analysis["data_flows"]))
        if analysis.get("gaps"):
            lines.append(
                "Potential weaknesses to probe (verify against the diagram before "
                "asking; pick the most important one): " + " | ".join(analysis["gaps"])
            )
        if analysis.get("last_change"):
            lines.append(
                "The candidate JUST changed the diagram: "
                + analysis["last_change"]
                + ". React to this specific change in your next question."
            )
    lines.append(
        "Ground your next question in SPECIFIC components/connections above (name "
        "them). Prefer probing a real gap over a generic question."
    )
    return "\n".join(lines)


def summarize_for_grader(session) -> str:
    """Condense the final diagram understanding for the evaluation."""
    model = getattr(session, "diagram_model", None)
    analysis = getattr(session, "diagram_analysis", None)
    if not model and not analysis:
        return ""
    out = ["Final whiteboard architecture:"]
    if model:
        out.append(diagram_to_text(model))
    if analysis and analysis.get("gaps"):
        out.append("Observed weaknesses: " + " | ".join(analysis["gaps"]))
    return "\n".join(out)


# --- Backward-compatible helpers still referenced elsewhere ---
def analyze_frame(source: str, image_data_url: str, hint: str = "") -> dict:
    """Legacy entry (image-only). Returns {note, flags} shape."""
    a = analyze_architecture(image_data_url, None, hint)
    note = a.get("summary", "")
    if a.get("gaps"):
        note += " Gaps: " + "; ".join(a["gaps"])
    return {"note": note, "flags": a.get("flags", [])}


def latest_screen_note(observations: list[dict]) -> str:
    for o in reversed(observations or []):
        if o.get("source") in ("screen", "diagram") and o.get("note"):
            return o["note"]
    return ""


def summarize_observations(observations: list[dict]) -> str:
    notes = [
        o
        for o in (observations or [])
        if o.get("source") in ("screen", "diagram") and o.get("note")
    ]
    if not notes:
        return ""
    lines = [f"- {o['note']}" for o in notes]
    return "What the candidate drew on the whiteboard:\n" + "\n".join(lines)
