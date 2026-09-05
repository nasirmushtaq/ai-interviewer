"""Tests for the system-design evaluation: the full rubric with teaching
('how a strong candidate reasons') and the 14 scoring dimensions."""

from conftest import requires_llm

from app import services

DESIGN_DIMENSIONS = {
    "requirements",
    "estimation",
    "api_data_model",
    "high_level_architecture",
    "data_flow",
    "storage_consistency",
    "caching_performance",
    "availability_fault_tolerance",
    "scalability_partitioning",
    "concurrency_distributed",
    "security_reliability",
    "operations",
    "tradeoffs",
    "communication",
}


@requires_llm
def test_design_evaluation_has_full_rubric_and_teaching():
    transcript = [
        {"role": "assistant", "text": "Design a URL shortener for millions of users."},
        {
            "role": "user",
            "text": "Client -> gateway -> a service storing short->long in Postgres. I added a Redis cache. Millions of users.",
        },
        {"role": "assistant", "text": "How do you generate unique short codes across servers?"},
        {"role": "user", "text": "Um, random strings and check the DB."},
    ]
    report = services.grade_interview(
        "SDE",
        "system_design",
        "hard",
        transcript,
        track="sde",
    )
    # 14 design dimensions scored
    scored = set(report.get("scores", {}).keys())
    missing = DESIGN_DIMENSIONS - scored
    assert not missing, f"Design rubric missing dimensions: {missing}"

    # Teaching rubric present with 'how a strong candidate reasons'
    rubric = report.get("rubric", [])
    assert rubric, "No teaching rubric returned for a design interview."
    assert any(
        r.get("how_a_strong_candidate_reasons") for r in rubric
    ), "Rubric entries lack 'how a strong candidate reasons' teaching."

    # Overall score is a sane int
    assert isinstance(report["overall_score"], int)
    assert 0 <= report["overall_score"] <= 100


@requires_llm
def test_coding_evaluation_uses_simple_rubric_not_design():
    """A DSA interview should NOT use the 14-dimension design rubric."""
    transcript = [
        {"role": "assistant", "text": "Reverse a linked list."},
        {"role": "user", "text": "Iterate with prev/cur/next pointers, O(n)/O(1)."},
    ]
    report = services.grade_interview(
        "SDE",
        "dsa",
        "medium",
        transcript,
        track="sde",
    )
    scored = set(report.get("scores", {}).keys())
    # coding uses the classic 4-dimension rubric
    assert "problem_solving" in scored
    assert "requirements" not in scored  # not the design rubric
