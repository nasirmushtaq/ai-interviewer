"""Tests for the diagram intelligence: structured graph analysis, diffing, and
the 'react only when meaningful' gating."""
from conftest import requires_llm, covers_any

from app import vision_service as v


# ---- Pure-logic tests (no LLM needed) ----
def test_diff_detects_added_component_and_edge():
    prev = {
        "components": [{"label": "Client"}, {"label": "Service"}],
        "edges": [{"from": "Client", "to": "Service"}],
    }
    curr = {
        "components": [{"label": "Client"}, {"label": "Service"}, {"label": "Redis"}],
        "edges": [{"from": "Client", "to": "Service"}, {"from": "Service", "to": "Redis"}],
    }
    diff = v.diff_models(prev, curr)
    assert diff["added_components"] == ["Redis"]
    assert "Service->Redis" in diff["added_connections"]
    assert diff["removed_components"] == []
    assert v.has_changes(diff) is True


def test_diff_no_change_is_empty():
    m = {"components": [{"label": "A"}], "edges": []}
    diff = v.diff_models(m, m)
    assert not v.has_changes(diff)


def test_diagram_to_text_renders_components_and_edges():
    m = {
        "components": [{"label": "Client"}, {"label": "DB"}],
        "edges": [{"from": "Client", "to": "DB"}],
        "loose_labels": ["millions of users"],
    }
    txt = v.diagram_to_text(m)
    assert "Client" in txt and "DB" in txt and "Client → DB" in txt


# ---- LLM behavior tests ----
@requires_llm
def test_architecture_analysis_flags_spof_and_missing_pieces():
    """A single-service-single-DB design should be read as having real gaps."""
    structure = {
        "components": [
            {"label": "Client"}, {"label": "OrderService"}, {"label": "Postgres"},
        ],
        "edges": [
            {"from": "Client", "to": "OrderService"},
            {"from": "OrderService", "to": "Postgres"},
        ],
        "loose_labels": ["millions of users"],
    }
    a = v.analyze_architecture("", structure, "system design whiteboard")
    gaps_text = " ".join(a.get("gaps", [])).lower()
    assert a.get("components"), "analysis returned no components"
    assert covers_any(gaps_text, [
        "bottleneck", "single point of failure", "spof", "replication",
        "no cache", "caching", "scale", "no queue", "single",
    ]), f"Analysis missed obvious gaps.\n---\n{a.get('gaps')}"


@requires_llm
def test_reaction_stays_silent_on_no_change():
    diff = v.diff_models({"components": [], "edges": []}, {"components": [], "edges": []})
    r = v.decide_reaction(diff, {"components": []}, {}, "")
    assert r["react"] is False


@requires_llm
def test_reaction_fires_on_significant_change():
    """Adding a single-point-of-failure component should warrant a reaction."""
    prev = {
        "components": [{"label": "Client"}, {"label": "Service"}],
        "edges": [{"from": "Client", "to": "Service"}],
    }
    curr = {
        "components": [
            {"label": "Client"}, {"label": "Service"},
            {"label": "PaymentProcessor"}, {"label": "Postgres (single)"},
        ],
        "edges": [
            {"from": "Client", "to": "Service"},
            {"from": "Service", "to": "PaymentProcessor"},
            {"from": "PaymentProcessor", "to": "Postgres (single)"},
        ],
        "loose_labels": ["millions of users, all payments through PaymentProcessor"],
    }
    diff = v.diff_models(prev, curr)
    analysis = v.analyze_architecture("", curr, "whiteboard")
    r = v.decide_reaction(diff, curr, analysis, "")
    assert r["react"] is True, f"Expected a reaction to the SPOF change. reason={r.get('reason')}"
    assert r["message"], "Reaction fired but produced no message."
