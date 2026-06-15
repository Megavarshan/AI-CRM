"""Channel Service — Application settings (real email + SMS/WhatsApp gateway)."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    REDIS_URL: str = "redis://localhost:6379/0"
    CRM_RECEIPT_URL: str = "http://localhost:8000/api/v1/receipts"
    PORT: int = 8001
    DEBUG: bool = False
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # ── Email (SMTP) ──────────────────────────────────────────────────────
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True          # STARTTLS on 587; set False for 1025 test server
    SMTP_USE_SSL: bool = False         # SSL on 465
    EMAIL_FROM: Optional[str] = None   # defaults to SMTP_USERNAME if unset
    EMAIL_FROM_NAME: str = "Orbit"

    # ── SMS / WhatsApp (Twilio) ───────────────────────────────────────────
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_SMS_FROM: Optional[str] = None        # e.g. +1XXXXXXXXXX
    TWILIO_WHATSAPP_FROM: Optional[str] = None   # e.g. whatsapp:+14155238886 (sandbox)

    @property
    def email_configured(self) -> bool:
        return bool(self.SMTP_HOST)

    @property
    def twilio_configured(self) -> bool:
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN)

    @property
    def email_from_addr(self) -> Optional[str]:
        return self.EMAIL_FROM or self.SMTP_USERNAME


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
