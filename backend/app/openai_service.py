"""Provider-agnostic wrappers around OpenAI / Azure OpenAI: text chat, vision,
realtime session bootstrap, memory extraction and interview grading.

Supports both standard OpenAI (api.openai.com) and Azure OpenAI, chosen via
config (auto-detected from env). For Azure, the `model` argument is the
*deployment name*.
"""
import json

import httpx
from openai import OpenAI, AzureOpenAI

from .config import settings

_client = None


def client():
    """Lazily build the right client for the configured provider."""
    global _client
    if _client is not None:
        return _client
    if settings.is_azure:
        _client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    elif settings.is_github:
        # GitHub Models is OpenAI-compatible: base OpenAI client + custom base_url,
        # authed with a GitHub PAT.
        _client = OpenAI(
            api_key=settings.GITHUB_TOKEN,
            base_url=settings.GITHUB_MODELS_ENDPOINT,
        )
    elif settings.is_ollama:
        # Local Ollama exposes an OpenAI-compatible API; no real key needed.
        _client = OpenAI(api_key="ollama", base_url=settings.OLLAMA_ENDPOINT)
    else:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def has_key() -> bool:
    if settings.is_azure:
        return bool(settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT)
    if settings.is_github:
        return bool(settings.GITHUB_TOKEN)
    if settings.is_ollama:
        return True  # local, no key required
    return bool(settings.OPENAI_API_KEY)


def _chat_model() -> str:
    if settings.is_azure:
        return settings.AZURE_OPENAI_CHAT_DEPLOYMENT
    if settings.is_github:
        return settings.GITHUB_MODELS_CHAT_MODEL
    if settings.is_ollama:
        return settings.OLLAMA_CHAT_MODEL
    return settings.OPENAI_TEXT_MODEL


def _vision_model() -> str:
    if settings.is_azure:
        return (
            settings.AZURE_OPENAI_VISION_DEPLOYMENT
            or settings.AZURE_OPENAI_CHAT_DEPLOYMENT
        )
    if settings.is_github:
        return settings.GITHUB_MODELS_VISION_MODEL
    if settings.is_ollama:
        return settings.OLLAMA_VISION_MODEL
    return settings.OPENAI_VISION_MODEL


def realtime_available() -> bool:
    if not has_key():
        return False
    if settings.is_azure:
        return bool(
            settings.AZURE_OPENAI_REALTIME_ENDPOINT
            and settings.AZURE_OPENAI_REALTIME_DEPLOYMENT
        )
    if settings.is_github or settings.is_ollama:
        return False  # no realtime voice endpoint
    return True  # standard OpenAI realtime is available with the API key


# Some models (e.g. the gpt-5 family) reject a custom `temperature` and only
# allow the default. We remember that per-model and transparently retry so the
# app is plug-and-play across model families.
_no_temperature_models: set[str] = set()


def _completion(model: str, temperature: float | None = None, **kwargs):
    """Chat-completion call that is tolerant of models which don't support a
    custom temperature — it strips it and retries once."""
    args = dict(kwargs)
    args["model"] = model
    if temperature is not None and model not in _no_temperature_models:
        args["temperature"] = temperature
    try:
        return client().chat.completions.create(**args)
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "temperature" in msg and ("unsupported" in msg or "does not support" in msg):
            _no_temperature_models.add(model)
            args.pop("temperature", None)
            return client().chat.completions.create(**args)
        raise


async def create_realtime_session(instructions: str, voice: str) -> dict:
    """Mint an ephemeral realtime session token for the browser.

    Returns a dict shaped like OpenAI's realtime session object, augmented with a
    `webrtc_url` the client should POST its SDP offer to.
    """
    if settings.is_azure:
        return await _create_azure_realtime_session(instructions, voice)
    return await _create_openai_realtime_session(instructions, voice)


async def _create_openai_realtime_session(instructions: str, voice: str) -> dict:
    url = "https://api.openai.com/v1/realtime/sessions"
    payload = {
        "model": settings.OPENAI_REALTIME_MODEL,
        "voice": voice,
        "instructions": instructions,
        "modalities": ["audio", "text"],
        "input_audio_transcription": {"model": "whisper-1"},
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    data["webrtc_url"] = (
        f"https://api.openai.com/v1/realtime?model={settings.OPENAI_REALTIME_MODEL}"
    )
    data["provider"] = "openai"
    return data


async def _create_azure_realtime_session(instructions: str, voice: str) -> dict:
    """Azure exposes realtime sessions under the deployment. Mint an ephemeral
    key via the sessions endpoint on the realtime resource."""
    base = settings.AZURE_OPENAI_REALTIME_ENDPOINT.rstrip("/")
    # Normalize wss:// -> https:// for the REST session-mint call.
    rest_base = base.replace("wss://", "https://").replace("ws://", "http://")
    api_version = settings.AZURE_OPENAI_REALTIME_API_VERSION
    deployment = settings.AZURE_OPENAI_REALTIME_DEPLOYMENT
    url = (
        f"{rest_base}/openai/realtimeapi/sessions"
        f"?api-version={api_version}"
    )
    payload = {
        "model": deployment,
        "voice": voice,
        "instructions": instructions,
        "modalities": ["audio", "text"],
        "input_audio_transcription": {"model": "whisper-1"},
    }
    headers = {
        "api-key": settings.AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    # WebRTC/SDP endpoint for Azure realtime.
    data["webrtc_url"] = (
        f"{rest_base}/openai/realtime"
        f"?api-version={api_version}&deployment={deployment}"
    )
    data["provider"] = "azure"
    return data


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
