"""Service-layer tests for :mod:`app.interview_service`.

These exercise the orchestration that used to live inside the route handlers —
prompt assembly, session-override resolution, persistence and error mapping —
with the LLM calls mocked out, so they run fast and offline (no key required).
"""

import asyncio
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db as database
from app import interview_service as svc
from app.errors import NotConfiguredError, UpstreamError
from app.schemas import ChatIn, CoachingIn, GradeIn, RealtimeIn, SaveConversationIn


@pytest.fixture
def db(tmp_path):
    """An isolated, per-test SQLite database bound to the real models."""
    engine = create_engine(
        f"sqlite:///{tmp_path/'test.db'}", connect_args={"check_same_thread": False}
    )
    database.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def user(db):
    u = database.User(username="alice")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# --------------------------------------------------------------------------- #
# generate_chat_reply
# --------------------------------------------------------------------------- #
def test_chat_requires_configured_provider(db, monkeypatch):
    monkeypatch.setattr(svc.ai, "has_key", lambda: False)
    with pytest.raises(NotConfiguredError):
        svc.generate_chat_reply(db, ChatIn(username="alice", mode="interview", message="hi"), None)


def test_chat_builds_system_history_and_final_message(db, monkeypatch):
    captured = {}
    monkeypatch.setattr(svc.ai, "has_key", lambda: True)

    def _fake_chat(messages):
        captured["m"] = messages
        return "REPLY"

    monkeypatch.setattr(svc.ai, "chat", _fake_chat)

    body = ChatIn(
        username="alice",
        mode="interview",
        message="my final answer",
        history=[
            {"role": "assistant", "text": "first question"},
            {"role": "user", "text": "candidate reply"},
        ],
    )
    reply = svc.generate_chat_reply(db, body, None)

    assert reply == "REPLY"
    msgs = captured["m"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"]
    # History is mapped to alternating roles, unknown roles coerced to "user".
    assert msgs[1] == {"role": "assistant", "content": "first question"}
    assert msgs[2] == {"role": "user", "content": "candidate reply"}
    # The current message is always appended last as the user turn.
    assert msgs[-1] == {"role": "user", "content": "my final answer"}


# --------------------------------------------------------------------------- #
# grade_session
# --------------------------------------------------------------------------- #
_FAKE_REPORT = {
    "overall_score": 72,
    "scores": {"communication": 70},
    "strengths": ["clear"],
    "improvements": ["scale"],
    "rubric": [],
    "feedback": "solid attempt",
    "hints_used": 0,
    "hint_penalty": 0,
}


def test_grade_persists_report_and_conversation(db, user, monkeypatch):
    monkeypatch.setattr(svc.services, "grade_interview", lambda *a, **k: dict(_FAKE_REPORT))

    body = GradeIn(
        username="alice",
        role="SDE",
        focus="dsa",
        difficulty="medium",
        transcript=[{"role": "user", "text": "hello"}],
    )
    result = svc.grade_session(db, body, user)

    assert result["overall_score"] == 72
    row = db.get(database.InterviewReport, result["id"])
    assert row is not None and row.user_id == user.id
    # The transcript is also persisted as a conversation for history/replay.
    convos = db.query(database.Conversation).filter_by(user_id=user.id, mode="interview").all()
    assert len(convos) == 1


def test_grade_prefers_session_setup_over_request(db, user, monkeypatch):
    seen = {}

    def _fake_grade(role, focus, difficulty, *a, **k):
        seen.update(role=role, focus=focus, difficulty=difficulty)
        return dict(_FAKE_REPORT)

    monkeypatch.setattr(svc.services, "grade_interview", _fake_grade)

    sess = database.Session(
        id="sess1",
        user_id=user.id,
        mode="interview",
        track="sde",
        role="Staff SDE",
        focus="system_design",
        difficulty="hard",
        transcript=[{"role": "user", "text": "from session"}],
    )
    db.add(sess)
    db.commit()

    body = GradeIn(username="alice", role="SDE", focus="dsa", difficulty="easy", session_id="sess1")
    svc.grade_session(db, body, user)

    # Stored session setup wins over the (stale) request fields.
    assert seen == {"role": "Staff SDE", "focus": "system_design", "difficulty": "hard"}
    # Grading finalises the session.
    db.refresh(sess)
    assert sess.status == "ended" and sess.ended_at is not None


# --------------------------------------------------------------------------- #
# save_conversation / coaching / realtime
# --------------------------------------------------------------------------- #
def test_save_persona_conversation_extracts_memories(db, user, monkeypatch):
    monkeypatch.setattr(
        svc.services,
        "summarize_and_extract",
        lambda transcript: {"summary": "a chat", "memories": ["likes tea", "from London"]},
    )
    body = SaveConversationIn(
        username="alice",
        mode="persona",
        persona_id="emma",
        transcript=[{"role": "user", "text": "hi"}],
    )
    out = svc.save_conversation(db, body, user)

    assert out["new_memories"] == ["likes tea", "from London"]
    assert db.query(database.Memory).filter_by(user_id=user.id).count() == 2


def test_coaching_delegates_with_session_overrides(db, user, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        svc.services,
        "generate_coaching",
        lambda role, focus, difficulty, transcript, **k: seen.update(
            role=role, focus=focus, transcript=transcript
        )
        or {"ok": True},
    )
    sess = database.Session(
        id="s2",
        user_id=user.id,
        mode="interview",
        role="Senior SDE",
        focus="system_design",
        difficulty="hard",
        transcript=[{"role": "user", "text": "stored"}],
    )
    db.add(sess)
    db.commit()

    out = svc.generate_coaching(db, CoachingIn(session_id="s2"))
    assert out == {"ok": True}
    assert seen["role"] == "Senior SDE" and seen["focus"] == "system_design"
    assert seen["transcript"] == [{"role": "user", "text": "stored"}]


def test_realtime_requires_provider(db, monkeypatch):
    monkeypatch.setattr(svc.ai, "has_key", lambda: False)
    with pytest.raises(NotConfiguredError):
        asyncio.run(svc.create_realtime_session(db, RealtimeIn(username="alice", mode="interview")))


def test_realtime_wraps_provider_failure_as_upstream(db, monkeypatch):
    monkeypatch.setattr(svc.ai, "has_key", lambda: True)
    monkeypatch.setattr(svc.ai, "realtime_available", lambda: True)

    async def _boom(instructions, voice):
        raise RuntimeError("provider down")

    monkeypatch.setattr(svc.ai, "create_realtime_session", _boom)
    with pytest.raises(UpstreamError):
        asyncio.run(svc.create_realtime_session(db, RealtimeIn(username="alice", mode="interview")))
