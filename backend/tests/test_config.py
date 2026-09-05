"""Config unit tests — offline, no LLM key required."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings


def test_semantic_vad_used_for_openai():
    td = Settings(REALTIME_VAD_MODE="semantic_vad").realtime_turn_detection("openai")
    assert td["type"] == "semantic_vad"
    # Barge-in must be enabled so the candidate can interrupt the AI.
    assert td["interrupt_response"] is True
    assert td["create_response"] is True


def test_semantic_vad_falls_back_to_server_vad_off_openai():
    # Azure has no semantic_vad — must degrade gracefully, not emit an invalid type.
    td = Settings(REALTIME_VAD_MODE="semantic_vad").realtime_turn_detection("azure")
    assert td["type"] == "server_vad"
    assert td["silence_duration_ms"] == 700
    assert td["interrupt_response"] is True


def test_server_vad_mode_is_honoured_on_openai():
    td = Settings(REALTIME_VAD_MODE="server_vad").realtime_turn_detection("openai")
    assert td["type"] == "server_vad"


def test_vad_params_are_configurable():
    td = Settings(
        REALTIME_VAD_MODE="server_vad", REALTIME_VAD_SILENCE_MS=1200
    ).realtime_turn_detection("openai")
    assert td["silence_duration_ms"] == 1200
