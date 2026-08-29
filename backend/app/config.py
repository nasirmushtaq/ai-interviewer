from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ----- Provider selection ("openai" or "azure"; auto-detected if blank) -----
    LLM_PROVIDER: str = ""  # leave blank to auto-detect from the vars below

    # ----- Standard OpenAI -----
    OPENAI_API_KEY: str = ""

    # ----- GitHub Models (OpenAI-compatible; auth with a GitHub PAT) -----
    # For prototyping/testing only. Get a token at https://github.com/settings/tokens
    # (fine-grained token with "Models" read access), then set GITHUB_TOKEN.
    GITHUB_TOKEN: str = ""
    GITHUB_MODELS_ENDPOINT: str = "https://models.inference.ai.azure.com"
    GITHUB_MODELS_CHAT_MODEL: str = "gpt-4o"
    GITHUB_MODELS_VISION_MODEL: str = "gpt-4o"

    # ----- Local Ollama (OpenAI-compatible; free, offline; no realtime voice) -----
    # Set LLM_PROVIDER=ollama (or it auto-selects if only Ollama is reachable).
    OLLAMA_ENDPOINT: str = "http://localhost:11434/v1"
    OLLAMA_CHAT_MODEL: str = "qwen3:8b"
    OLLAMA_VISION_MODEL: str = "qwen2.5vl:7b"

    # ----- Azure OpenAI -----
    # e.g. https://YOUR-RESOURCE.openai.azure.com
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    # Azure uses *deployment names* rather than model names.
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = "gpt-4o"
    AZURE_OPENAI_VISION_DEPLOYMENT: str = ""  # defaults to the chat deployment
    # Realtime (voice) — often a different region/resource. Leave blank to disable.
    AZURE_OPENAI_REALTIME_ENDPOINT: str = ""   # wss://...  or https://...
    AZURE_OPENAI_REALTIME_DEPLOYMENT: str = ""
    AZURE_OPENAI_REALTIME_API_VERSION: str = "2024-10-01-preview"

    # ----- Model names (used for standard OpenAI) -----
    OPENAI_TEXT_MODEL: str = "gpt-4o"
    OPENAI_VISION_MODEL: str = "gpt-4o"
    OPENAI_REALTIME_MODEL: str = "gpt-4o-realtime-preview"

    # ----- App environment / server -----
    ENV: str = "development"  # "development" | "production"
    LOG_LEVEL: str = "INFO"
    # CORS allowed origins: comma-separated list, or "*" for any.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ----- Feature flags -----
    # Which interview tracks are available. Comma-separated track ids, or "*"
    # for all. Default: SDE only (focus the product). Non-listed tracks are
    # hidden from the catalog and rejected server-side.
    ENABLED_TRACKS: str = "sde"
    # Whether the persona / English-practice calls are available.
    ENABLE_PERSONA_CALLS: bool = False

    def enabled_tracks_list(self) -> list[str]:
        raw = (self.ENABLED_TRACKS or "").strip()
        if raw == "*" or not raw:
            return ["*"]
        return [t.strip().lower() for t in raw.split(",") if t.strip()]

    def is_track_enabled(self, track_id: str | None) -> bool:
        allowed = self.enabled_tracks_list()
        if allowed == ["*"]:
            return True
        return (track_id or "").lower() in allowed

    # ----- Auth (JWT) -----
    JWT_SECRET: str = "dev-insecure-change-me"
    JWT_ALG: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    # If true, interview/session endpoints require a logged-in user.
    REQUIRE_AUTH: bool = False

    # ----- Rate limiting (per client IP) -----
    RATE_LIMIT_LLM: str = "30/minute"   # chat / grade / hints
    RATE_LIMIT_EXEC: str = "20/minute"  # run / submit code

    # ----- Billing / payments -----
    # Number of free interviews a new user gets before the paywall.
    FREE_INTERVIEW_QUOTA: int = 2
    # Test/dev only: allow instantly granting credits WITHOUT a real payment via
    # /api/billing/dev-grant. HARD-DISABLED in production regardless of value.
    DEV_ALLOW_TEST_PAYMENTS: bool = False
    # Currency for orders (INR for Razorpay/Cashfree).
    BILLING_CURRENCY: str = "INR"
    # Active provider for new orders: "razorpay" | "cashfree".
    PAYMENT_PROVIDER: str = "razorpay"

    # Razorpay (test/sandbox keys start with rzp_test_)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Cashfree (sandbox)
    CASHFREE_APP_ID: str = ""
    CASHFREE_SECRET_KEY: str = ""
    CASHFREE_WEBHOOK_SECRET: str = ""
    CASHFREE_ENV: str = "sandbox"  # "sandbox" | "production"

    FRONTEND_ORIGIN: str = "http://localhost:5173"
    DATABASE_URL: str = "sqlite:///./linguacall.db"

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in ("production", "prod")

    def cors_origins_list(self) -> list[str]:
        raw = (self.CORS_ORIGINS or "").strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    # Shared secret the media service uses to POST frames to the core API.
    MEDIA_SERVICE_TOKEN: str = "dev-media-token"
    # Where the media (mediasoup) service lives, for clients that ask.
    MEDIA_SERVICE_URL: str = "http://localhost:4000"

    # Self-hosted Piston code-execution service (cgroup v2 compatible).
    PISTON_URL: str = "http://localhost:2000"

    # Redis for cross-instance pub/sub (live observation streaming) and caching.
    # Leave blank to use an in-memory fallback (single-instance dev only).
    REDIS_URL: str = ""

    # Trim accidental whitespace / surrounding quotes from every string value so
    # a copy-pasted key or endpoint "just works".
    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, v):
        if isinstance(v, str):
            return v.strip().strip('"').strip("'")
        return v

    @property
    def _has_azure(self) -> bool:
        return bool(self.AZURE_OPENAI_API_KEY and self.AZURE_OPENAI_ENDPOINT)

    @property
    def _has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def _has_github(self) -> bool:
        return bool(self.GITHUB_TOKEN)

    @property
    def provider(self) -> str:
        """Plug-and-play provider resolution:
        1. Honor an explicit, usable LLM_PROVIDER.
        2. Otherwise pick whichever set of credentials is actually present
           (priority: azure, then openai, then github-models)."""
        forced = (self.LLM_PROVIDER or "").lower()
        if forced in ("github", "github-models", "github_models"):
            forced = "github"
        if forced == "ollama":
            return "ollama"  # local, no key required
        if forced == "azure" and self._has_azure:
            return "azure"
        if forced == "openai" and self._has_openai:
            return "openai"
        if forced == "github" and self._has_github:
            return "github"
        # Auto-detect from whatever credentials were dropped in.
        if self._has_azure:
            return "azure"
        if self._has_openai:
            return "openai"
        if self._has_github:
            return "github"
        return forced or "openai"

    @property
    def is_azure(self) -> bool:
        return self.provider == "azure"

    @property
    def is_github(self) -> bool:
        return self.provider == "github"

    @property
    def is_ollama(self) -> bool:
        return self.provider == "ollama"

    def provider_status(self) -> dict:
        """Human-readable diagnostics for the /api/health and startup log."""
        return {
            "provider": self.provider,
            "openai_configured": self._has_openai,
            "azure_configured": self._has_azure,
            "github_configured": self._has_github,
            "forced": bool(self.LLM_PROVIDER),
        }


settings = Settings()
