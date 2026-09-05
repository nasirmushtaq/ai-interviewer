"""Concrete LLM provider strategies. Add a new provider by adding a class here
and registering it in registry.py — nothing else changes."""

from __future__ import annotations

import httpx
from openai import AzureOpenAI, OpenAI

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def configured(self) -> bool:
        return bool(self.settings.OPENAI_API_KEY)

    def build_client(self):
        return OpenAI(api_key=self.settings.OPENAI_API_KEY)

    def chat_model(self) -> str:
        return self.settings.OPENAI_TEXT_MODEL

    def vision_model(self) -> str:
        return self.settings.OPENAI_VISION_MODEL

    def supports_realtime(self) -> bool:
        return self.configured()

    async def create_realtime_session(self, instructions: str, voice: str) -> dict:
        s = self.settings
        url = "https://api.openai.com/v1/realtime/sessions"
        payload = {
            "model": s.OPENAI_REALTIME_MODEL,
            "voice": voice,
            "instructions": instructions,
            "modalities": ["audio", "text"],
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": s.realtime_turn_detection(self.name),
        }
        headers = {
            "Authorization": f"Bearer {s.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        data["webrtc_url"] = f"https://api.openai.com/v1/realtime?model={s.OPENAI_REALTIME_MODEL}"
        data["provider"] = "openai"
        return data


class AzureProvider(LLMProvider):
    name = "azure"

    def configured(self) -> bool:
        return bool(self.settings.AZURE_OPENAI_API_KEY and self.settings.AZURE_OPENAI_ENDPOINT)

    def build_client(self):
        s = self.settings
        return AzureOpenAI(
            api_key=s.AZURE_OPENAI_API_KEY,
            azure_endpoint=s.AZURE_OPENAI_ENDPOINT,
            api_version=s.AZURE_OPENAI_API_VERSION,
        )

    def chat_model(self) -> str:
        return self.settings.AZURE_OPENAI_CHAT_DEPLOYMENT

    def vision_model(self) -> str:
        s = self.settings
        return s.AZURE_OPENAI_VISION_DEPLOYMENT or s.AZURE_OPENAI_CHAT_DEPLOYMENT

    def supports_realtime(self) -> bool:
        s = self.settings
        return bool(s.AZURE_OPENAI_REALTIME_ENDPOINT and s.AZURE_OPENAI_REALTIME_DEPLOYMENT)

    async def create_realtime_session(self, instructions: str, voice: str) -> dict:
        s = self.settings
        base = s.AZURE_OPENAI_REALTIME_ENDPOINT.rstrip("/")
        rest_base = base.replace("wss://", "https://").replace("ws://", "http://")
        api_version = s.AZURE_OPENAI_REALTIME_API_VERSION
        deployment = s.AZURE_OPENAI_REALTIME_DEPLOYMENT
        url = f"{rest_base}/openai/realtimeapi/sessions?api-version={api_version}"
        payload = {
            "model": deployment,
            "voice": voice,
            "instructions": instructions,
            "modalities": ["audio", "text"],
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": s.realtime_turn_detection(self.name),
        }
        headers = {"api-key": s.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        data["webrtc_url"] = (
            f"{rest_base}/openai/realtime" f"?api-version={api_version}&deployment={deployment}"
        )
        data["provider"] = "azure"
        return data


class OpenAICompatibleProvider(LLMProvider):
    """Any OpenAI-compatible endpoint (Kimi/Moonshot, DeepSeek, Together, Groq,
    Fireworks, ...). Driven entirely by CUSTOM_LLM_* config."""

    name = "openai_compatible"

    def configured(self) -> bool:
        s = self.settings
        return bool(s.CUSTOM_LLM_BASE_URL and s.CUSTOM_LLM_API_KEY and s.CUSTOM_LLM_CHAT_MODEL)

    def build_client(self):
        s = self.settings
        return OpenAI(api_key=s.CUSTOM_LLM_API_KEY, base_url=s.CUSTOM_LLM_BASE_URL)

    def chat_model(self) -> str:
        return self.settings.CUSTOM_LLM_CHAT_MODEL

    def vision_model(self) -> str:
        # Blank when the provider can't read images (e.g. Kimi K2).
        return self.settings.CUSTOM_LLM_VISION_MODEL


class GitHubModelsProvider(LLMProvider):
    name = "github"

    def configured(self) -> bool:
        return bool(self.settings.GITHUB_TOKEN)

    def build_client(self):
        s = self.settings
        return OpenAI(api_key=s.GITHUB_TOKEN, base_url=s.GITHUB_MODELS_ENDPOINT)

    def chat_model(self) -> str:
        return self.settings.GITHUB_MODELS_CHAT_MODEL

    def vision_model(self) -> str:
        return self.settings.GITHUB_MODELS_VISION_MODEL


class OllamaProvider(LLMProvider):
    name = "ollama"

    def configured(self) -> bool:
        return True  # local, no key required

    def build_client(self):
        return OpenAI(api_key="ollama", base_url=self.settings.OLLAMA_ENDPOINT)

    def chat_model(self) -> str:
        return self.settings.OLLAMA_CHAT_MODEL

    def vision_model(self) -> str:
        return self.settings.OLLAMA_VISION_MODEL
