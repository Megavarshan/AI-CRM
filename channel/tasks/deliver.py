"""
Celery task — REAL message delivery.

Replaces the old probabilistic simulator. Actually sends the message
(email via SMTP, SMS/WhatsApp via Twilio) and fires a single truthful receipt
back to the CRM: 'delivered' if the provider accepted it, else 'failed' with
the real reason. Opens and clicks are NOT invented here — they arrive later as
genuine events on the CRM's tracking endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from celery_app import app
from config import settings
from senders import send_email, send_twilio

logger = logging.getLogger(__name__)


def _fire_receipt(payload: dict, status: str, reason: str | None = None) -> None:
    base_key = payload["idempotency_key"]
    data = {
        "communication_id": payload["communication_id"],
        "campaign_id": payload["campaign_id"],
        "idempotency_key": f"{base_key}_{status}",
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if reason:
        data["failure_reason"] = reason
    try:
        httpx.post(settings.CRM_RECEIPT_URL, json=data, timeout=15).raise_for_status()
    except Exception as e:  # noqa: BLE001
        logger.warning("Receipt callback failed for %s (%s): %s", payload["communication_id"], status, e)


@app.task(name="tasks.deliver.deliver_message", bind=True, max_retries=2, default_retry_delay=20)
def deliver_message(self, payload: dict) -> None:
    """Actually send one message, then report delivered/failed."""
    channel = payload.get("channel", "email")

    if channel == "email":
        ok, reason = send_email(
            to_addr=payload.get("recipient_email") or "",
            subject=payload.get("subject") or "A message for you",
            html_body=payload.get("html_body") or payload.get("message") or "",
            text_body=payload.get("message"),
        )
    elif channel in ("sms", "whatsapp", "rcs"):
        ok, reason = send_twilio(
            channel=channel,
            to_number=payload.get("recipient_phone") or "",
            body=payload.get("message") or "",
        )
    else:
        ok, reason = False, f"unsupported channel: {channel}"

    _fire_receipt(payload, "delivered" if ok else "failed", None if ok else reason)
