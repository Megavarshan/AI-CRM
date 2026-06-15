"""
Channel Service — FastAPI entry point.

A completely separate process from the CRM service.
Receives send requests, accepts them immediately (202),
and delegates delivery simulation to Celery.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from routers import send


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Orbit Channel Service",
    description="Real messaging gateway: sends email (SMTP) and SMS/WhatsApp (Twilio), reports delivery.",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(send.router, tags=["Send"])


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok", "service": "channel"}


@app.get("/channels/status", tags=["Health"])
async def channel_status() -> dict:
    """Which real channels are configured + ready to send."""
    return {
        "email": settings.email_configured,
        "sms": settings.twilio_configured and bool(settings.TWILIO_SMS_FROM),
        "whatsapp": settings.twilio_configured and bool(settings.TWILIO_WHATSAPP_FROM),
        "rcs": False,
    }
