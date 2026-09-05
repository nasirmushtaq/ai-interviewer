"""Public metadata endpoints: health, client bootstrap config, and the static
catalog of personas, tracks, companies, difficulties and hint tiers."""

from fastapi import APIRouter

from .. import catalog
from .. import openai_service as ai
from .. import personas as p
from ..config import settings

router = APIRouter(tags=["meta"])


@router.get("/api/health")
def health():
    return {
        "ok": True,
        "has_openai_key": ai.has_key(),
        "provider": settings.provider,
        "realtime_available": ai.realtime_available(),
    }


@router.get("/api/config")
def client_config():
    """Public config a web or native client needs to bootstrap."""
    return {
        "has_openai_key": ai.has_key(),
        "provider": settings.provider,
        "realtime_available": ai.realtime_available(),
        "media_service_url": settings.MEDIA_SERVICE_URL,
        "video_supported": True,
        "screenshare_supported": True,
        # Feature flags for the client to hide disabled features.
        "enabled_tracks": settings.enabled_tracks_list(),
        "persona_calls_enabled": settings.ENABLE_PERSONA_CALLS,
    }


@router.get("/api/personas")
def personas():
    # Persona/English-practice calls can be disabled via feature flag.
    if not settings.ENABLE_PERSONA_CALLS:
        return []
    return p.list_personas()


@router.get("/api/interview/focuses")
def focuses():
    return [{"id": k, "label": v} for k, v in p.INTERVIEW_FOCUS.items()]


@router.get("/api/catalog/tracks")
def catalog_tracks():
    """Interview tracks, filtered by the ENABLED_TRACKS feature flag."""
    return [t for t in catalog.list_tracks() if settings.is_track_enabled(t["id"])]


@router.get("/api/catalog/companies")
def catalog_companies():
    """Curated company/board profiles; clients may also send a free-text name."""
    return catalog.list_companies()


@router.get("/api/catalog/difficulties")
def catalog_difficulties():
    return [
        {"id": k, "label": v["label"], "question": v["question"]}
        for k, v in catalog.DIFFICULTY.items()
    ]


@router.get("/api/catalog/design-topics")
def catalog_design_topics():
    """Suggested staged-design problems (payment gateway, bank, etc.). Any
    free-text topic also works via candidate_note."""
    return catalog.DESIGN_TOPICS


@router.get("/api/catalog/hint-tiers")
def catalog_hint_tiers():
    return [
        {"tier": k, "label": v["label"], "penalty": v["penalty"], "reveal": v["reveal"]}
        for k, v in catalog.HINT_TIERS.items()
    ]
