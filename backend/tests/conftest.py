"""Shared test fixtures + helpers for interview-quality tests.

These tests exercise the REAL interviewer (they call the configured LLM), then
assert on observable BEHAVIOR — e.g. "across this conversation, did the
interviewer eventually probe unique-code generation and the DB schema?".

LLM output varies, so we assert on concepts (keyword/semantic coverage across a
short simulated conversation), not exact strings. Tests are skipped when no LLM
key is configured, so the suite still passes in CI without credentials.
"""

import os
import sys

import pytest

# Make `app` importable when running pytest from the backend dir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import openai_service as ai
from app import personas as p

requires_llm = pytest.mark.skipif(
    not ai.has_key(), reason="No LLM key configured; skipping live-model tests."
)


class Interviewer:
    """Drives a simulated system-design interview against the real model.

    Builds the same system prompt the app uses, then lets a test push candidate
    messages and collect interviewer replies. `all_text()` returns the full
    interviewer side for concept-coverage assertions.
    """

    def __init__(
        self,
        focus="system_design",
        difficulty="hard",
        track="sde",
        company_id=None,
        seed_history=None,
    ):
        self.system = p.build_interview_instructions(
            "SDE", focus, difficulty, track=track, company_id=company_id
        )
        # history is [{role, text}] like the app's /api/chat
        self.history = list(seed_history or [])

    def say(self, candidate_message: str) -> str:
        """Candidate says something; return the interviewer's reply."""
        messages = [{"role": "system", "content": self.system}]
        for turn in self.history:
            role = "assistant" if turn["role"] == "assistant" else "user"
            messages.append({"role": role, "content": turn["text"]})
        messages.append({"role": "user", "content": candidate_message})
        reply = ai.chat(messages, temperature=0.4)
        self.history.append({"role": "user", "text": candidate_message})
        self.history.append({"role": "assistant", "text": reply})
        return reply

    def interviewer_text(self) -> str:
        """All interviewer turns concatenated (lowercased) for coverage checks."""
        return "\n".join(t["text"] for t in self.history if t["role"] == "assistant").lower()


def covers_any(text: str, keywords: list[str]) -> bool:
    """True if the text mentions ANY of the keyword variants."""
    t = text.lower()
    return any(k.lower() in t for k in keywords)


def covers_all(text: str, keyword_groups: list[list[str]]) -> bool:
    """True if EACH group is matched by at least one of its variants."""
    return all(covers_any(text, group) for group in keyword_groups)
