"""LLM provider strategies.

Each provider is a self-contained strategy implementing `LLMProvider`. Selecting
a provider is config-driven (LLM_PROVIDER + credentials); adding a new provider
means adding ONE class and registering it — no scattered if/elif branches.

The primary (chat/reasoning) provider and the vision (image/diagram) provider can
differ, e.g. Kimi K2 for reasoning + OpenAI for vision.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

loglog = logging.getLogger("linguacall.providers")


class LLMProvider(ABC):
    """Strategy interface for an OpenAI-compatible chat/vision provider."""

    #: short stable id, e.g. "openai", "azure", "kimi"
    name: str = "base"

    def __init__(self, settings):
        self.settings = settings
        self._client = None

    # --- capability / readiness ---
    @abstractmethod
    def configured(self) -> bool:
        """True if this provider has the credentials/fields it needs."""

    def supports_vision(self) -> bool:
        return bool(self.vision_model())

    def supports_realtime(self) -> bool:
        return False

    # --- client + models ---
    @abstractmethod
    def build_client(self):
        """Construct and return the SDK client for this provider."""

    def client(self):
        if self._client is None:
            self._client = self.build_client()
        return self._client

    @abstractmethod
    def chat_model(self) -> str: ...

    @abstractmethod
    def vision_model(self) -> str: ...

    # --- realtime (optional) ---
    async def create_realtime_session(self, instructions: str, voice: str) -> dict:
        raise NotImplementedError(f"{self.name} has no realtime voice support.")
