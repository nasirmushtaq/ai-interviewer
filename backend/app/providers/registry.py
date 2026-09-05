"""Provider registry + config-driven resolution of the active primary (chat) and
vision providers. Adding a provider = register its class here."""

from __future__ import annotations

import logging

from .base import LLMProvider
from .strategies import (
    AzureProvider,
    GitHubModelsProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
)

log = logging.getLogger("linguacall.providers")

# Canonical provider id -> strategy class.
_REGISTRY: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "azure": AzureProvider,
    "github": GitHubModelsProvider,
    "ollama": OllamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
}

# Friendly aliases the user can put in LLM_PROVIDER / VISION_PROVIDER.
_ALIASES = {
    "github-models": "github",
    "github_models": "github",
    "custom": "openai_compatible",
    "compatible": "openai_compatible",
    "kimi": "openai_compatible",
    "moonshot": "openai_compatible",
    "deepseek": "openai_compatible",
    "together": "openai_compatible",
    "groq": "openai_compatible",
    "fireworks": "openai_compatible",
}

# Preference order when auto-detecting from whatever creds are present.
_AUTODETECT_ORDER = ["openai_compatible", "azure", "openai", "github"]

_instances: dict[str, LLMProvider] = {}


def _canonical(name: str | None) -> str | None:
    if not name:
        return None
    n = name.strip().lower()
    n = _ALIASES.get(n, n)
    return n if n in _REGISTRY else None


def get_provider(name: str, settings) -> LLMProvider:
    """Instantiate (and cache) a provider strategy by canonical name."""
    if name not in _instances:
        _instances[name] = _REGISTRY[name](settings)
    return _instances[name]


def reset_cache() -> None:
    _instances.clear()


def resolve_primary(settings) -> LLMProvider:
    """The primary chat/reasoning provider: honor LLM_PROVIDER if usable, else
    auto-detect from available credentials."""
    forced = _canonical(settings.LLM_PROVIDER)
    if forced:
        p = get_provider(forced, settings)
        if forced == "ollama" or p.configured():
            return p
    for cand in _AUTODETECT_ORDER:
        p = get_provider(cand, settings)
        if p.configured():
            return p
    # Nothing configured — return OpenAI so has_key()/errors stay meaningful.
    return get_provider("openai", settings)


def resolve_vision(settings) -> LLMProvider:
    """Provider for image/diagram analysis. Honor VISION_PROVIDER; else use the
    primary if it supports vision; else auto-fall-back to a vision-capable one."""
    forced = _canonical(settings.VISION_PROVIDER)
    if forced:
        return get_provider(forced, settings)
    primary = resolve_primary(settings)
    if primary.supports_vision():
        return primary
    # Primary can't read images (e.g. Kimi) — fall back to a capable provider.
    for cand in ("openai", "azure", "github"):
        p = get_provider(cand, settings)
        if p.configured() and p.supports_vision():
            log.info("vision: primary '%s' lacks vision; using '%s'", primary.name, cand)
            return p
    return primary  # nothing better available
