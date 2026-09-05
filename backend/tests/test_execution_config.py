"""Piston API base-URL normalization — offline, no LLM key required."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings


def test_piston_api_base_self_hosted_gets_api_v2():
    assert Settings(PISTON_URL="http://localhost:2000").piston_api_base == (
        "http://localhost:2000/api/v2"
    )


def test_piston_api_base_public_left_as_is():
    # The public instance already contains /api/v2 — must not be doubled.
    assert Settings(PISTON_URL="https://emkc.org/api/v2/piston").piston_api_base == (
        "https://emkc.org/api/v2/piston"
    )


def test_piston_api_base_strips_trailing_slash():
    assert Settings(PISTON_URL="http://piston:2000/").piston_api_base == (
        "http://piston:2000/api/v2"
    )
