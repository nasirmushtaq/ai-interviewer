"""Tests for the comprehensive-interview coverage state machine: checklists,
status tracking, and the interviewer refusing to wrap up with gaps."""
from conftest import requires_llm, covers_any

from app import checklists as c


# ---- Pure-logic (no LLM) ----
def test_url_shortener_checklist_includes_mandatory_lld_items():
    cov = c.init_coverage("url_shortener")
    items = [i["item"].lower() for i in cov["items"]]
    assert any("uniqueness" in i for i in items), "missing uniqueness item"
    assert any("schema" in i for i in items), "missing schema item"
    assert any("generation" in i for i in items), "missing code-generation item"


def test_topic_detection():
    assert c.detect_topic("Design a URL shortener like bit.ly") == "url_shortener"
    assert c.detect_topic("build a rate limiter") == "rate_limiter"
    assert c.detect_topic("design a news feed / timeline") == "news_feed"
    assert c.detect_topic("something totally custom") is None


def test_completeness_and_next_targets():
    cov = c.init_coverage("rate_limiter")
    assert c.is_complete(cov) is False  # nothing asked yet
    # mark everything asked -> complete
    for i in cov["items"]:
        i["status"] = "asked"
    assert c.is_complete(cov) is True
    # a single not_asked makes it incomplete again
    cov["items"][0]["status"] = "not_asked"
    assert c.is_complete(cov) is False
    assert c.next_targets(cov, 1)[0]["status"] == "not_asked"


def test_generic_checklist_for_unknown_system():
    cov = c.init_coverage(None)
    areas = {i["area"] for i in cov["items"]}
    # core system-design areas should all be present
    for a in ["requirements", "estimation", "high_level_architecture",
              "storage_consistency", "scalability_partitioning", "tradeoffs"]:
        assert a in areas, f"generic checklist missing area {a}"


# ---- Live: the interviewer refuses to end with gaps ----
@requires_llm
def test_interviewer_refuses_early_wrap_up_when_coverage_incomplete():
    """This exercises coverage.coverage_prompt_block directly against the model:
    given an incomplete checklist, the interviewer must NOT wrap up."""
    from app import personas as p
    from app import openai_service as ai
    from app import coverage as cov_engine

    cov = c.init_coverage("url_shortener")
    # candidate covered only a couple of things; most items not_asked
    block = cov_engine.coverage_prompt_block(cov)
    system = p.build_interview_instructions("SDE", "system_design", "hard", track="sde") + block

    messages = [
        {"role": "system", "content": system},
        {"role": "assistant", "content": "Design a URL shortener."},
        {"role": "user", "content": "I named the components. I think we're done, let's wrap up."},
    ]
    reply = ai.chat(messages, temperature=0.3).lower()
    # It should keep going / say there's more to cover, and NOT conclude.
    assert covers_any(reply, [
        "cover", "haven't", "not done", "let's continue", "more ground",
        "before we wrap", "keep going", "still", "requirement", "estimate",
        "schema", "next",
    ]), f"Interviewer wrapped up despite an incomplete checklist.\n---\n{reply}"


def test_transactional_systems_include_deep_db_concurrency():
    """Bank/payment/ticketing checklists must force isolation, locking, deadlocks."""
    for topic in ["bank", "payment_gateway", "ticketing"]:
        cov = c.init_coverage(topic)
        items = " ".join(i["item"].lower() for i in cov["items"])
        for concept in ["isolation", "lock", "deadlock", "transaction"]:
            assert concept in items, f"{topic} checklist missing '{concept}'"


def test_generic_design_has_transactions_area():
    cov = c.init_coverage(None)
    areas = {i["area"] for i in cov["items"]}
    assert "transactions_concurrency" in areas
    assert "indexing_storage_internals" in areas


def test_transactional_systems_include_distributed_failure_items():
    """Bank/payment must force the cross-system timeout/saga/outbox probes."""
    for topic in ["bank", "payment_gateway"]:
        cov = c.init_coverage(topic)
        items = " ".join(i["item"].lower() for i in cov["items"])
        for concept in ["saga", "outbox", "timed out", "reconcil", "idempot"]:
            assert concept in items, f"{topic} missing distributed concept '{concept}'"


def test_generic_design_has_distributed_and_resilience_areas():
    cov = c.init_coverage(None)
    areas = {i["area"] for i in cov["items"]}
    assert "distributed_transactions" in areas
    assert "service_resilience" in areas
