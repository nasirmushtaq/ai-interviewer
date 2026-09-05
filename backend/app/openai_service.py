"""Provider-agnostic wrappers around OpenAI-compatible LLMs: text chat, vision,
realtime session bootstrap, memory extraction and interview grading.

Provider selection uses the Strategy pattern (see app/providers/). The active
primary (chat) and vision providers are resolved from config; this module just
delegates to them, so there are no per-provider if/elif branches here.
"""

import json

from . import providers
from .config import settings


def _primary() -> "providers.LLMProvider":
    return providers.resolve_primary(settings)


def _vision() -> "providers.LLMProvider":
    return providers.resolve_vision(settings)


def client():
    """SDK client for the primary (chat/text) provider."""
    return _primary().client()


def vision_client():
    """SDK client for vision/diagram analysis (may be a different provider)."""
    return _vision().client()


def has_key() -> bool:
    return _primary().configured()


def _chat_model() -> str:
    return _primary().chat_model()


def _vision_model() -> str:
    return _vision().vision_model()


def realtime_available() -> bool:
    return has_key() and _primary().supports_realtime()


# Some models (e.g. the gpt-5 family) reject a custom `temperature` and only
# allow the default. We remember that per-model and transparently retry so the
# app is plug-and-play across model families.
_no_temperature_models: set[str] = set()


def _completion(model: str, temperature: float | None = None, _client=None, **kwargs):
    """Chat-completion call that is tolerant of models which don't support a
    custom temperature — it strips it and retries once. `_client` lets callers
    (e.g. vision) target a different provider's client."""
    cli = _client or client()
    args = dict(kwargs)
    args["model"] = model
    if temperature is not None and model not in _no_temperature_models:
        args["temperature"] = temperature
    try:
        return cli.chat.completions.create(**args)
    except Exception as e:
        msg = str(e).lower()
        if "temperature" in msg and ("unsupported" in msg or "does not support" in msg):
            _no_temperature_models.add(model)
            args.pop("temperature", None)
            return cli.chat.completions.create(**args)
        raise


async def create_realtime_session(instructions: str, voice: str) -> dict:
    """Mint an ephemeral realtime session token for the browser, delegating to the
    active provider's strategy. Returns a dict shaped like OpenAI's realtime
    session object, augmented with a `webrtc_url`."""
    return await _primary().create_realtime_session(instructions, voice)


def chat(messages: list[dict], temperature: float = 0.8) -> str:
    resp = _completion(_chat_model(), temperature=temperature, messages=messages)
    return resp.choices[0].message.content or ""


def vision_json(
    system: str, user_text: str, image_data_urls: list[str], temperature: float = 0.3
) -> dict:
    content: list[dict] = [{"type": "text", "text": user_text}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    resp = _completion(
        _vision_model(),
        temperature=temperature,
        _client=vision_client(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content or "{}")


def chat_json(messages: list[dict], temperature: float = 0.4) -> dict:
    resp = _completion(
        _chat_model(),
        temperature=temperature,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content or "{}")
