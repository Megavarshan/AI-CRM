"""
Orbit CRM — Application settings.

Reads from environment variables (or .env file via pydantic-settings).
Import `settings` wherever config values are needed.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Supabase ──────────────────────────────────────────────────────────
    # Made optional with None defaults to prevent import-time failures in test/CI environments
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None

    # ── Groq ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str | None = None

    # ── Redis / Celery ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    # When true, Celery runs tasks synchronously in-process with no broker.
    # Lets the full stack run without Redis (e.g. local dev without Docker).
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # ── Inter-service ─────────────────────────────────────────────────────
    CHANNEL_SERVICE_URL: str = "http://localhost:8001"
    # Public base URL where THIS service's tracking endpoints are reachable by
    # email recipients (open pixel, click redirect, unsubscribe). In production
    # set this to the deployed CRM URL; locally localhost works for self-tests.
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # ── App ───────────────────────────────────────────────────────────────
    PORT: int = 8000
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    # Kept as a raw string to avoid pydantic-settings trying to JSON-decode a
    # comma-separated env value (which would raise at startup). Use the parsed
    # `allowed_origins` property instead of this field directly.
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # ── LLM ───────────────────────────────────────────────────────────────
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    LLM_MAX_RETRIES: int = 3

    @property
    def allowed_origins(self) -> List[str]:
        """Parse ALLOWED_ORIGINS (comma-separated string or JSON array) into a list."""
        s = self.ALLOWED_ORIGINS.strip()
        if s.startswith("["):
            import json
            return json.loads(s)
        return [origin.strip() for origin in s.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()


# ── Lazy Supabase Client (singleton) ──────────────────────────────────────
from typing import Any  # noqa: E402

class LazySupabaseClient:
    """
    A lazy-loading proxy for the Supabase Client.
    Prevents crashing on module import if environment variables are not set
    (e.g., during tests, linting, or container building).
    """
    def __init__(self) -> None:
        self._client: Any = None

    def _get_inner_client(self) -> Any:
        if self._client is None:
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
                raise RuntimeError(
                    "Supabase environment variables are missing.\n"
                    "Please define SUPABASE_URL and SUPABASE_SERVICE_KEY in your .env file."
                )
            from supabase import create_client
            self._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        return self._client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_inner_client(), name)


supabase: Any = LazySupabaseClient()


# ── Lazy Redis Client (singleton) ─────────────────────────────────────────
class LazyRedisClient:
    """
    A lazy-loading proxy for the Redis Client.
    """
    def __init__(self) -> None:
        self._client: Any = None

    def _get_inner_client(self) -> Any:
        if self._client is None:
            import redis
            self._client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_inner_client(), name)


redis_client: Any = LazyRedisClient()
