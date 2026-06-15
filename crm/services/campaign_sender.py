"""
Campaign Sender — calls the channel service POST /send for each communication.
"""

from __future__ import annotations

import httpx

from config import settings


async def send_message(
    communication_id: str,
    campaign_id: str,
    customer_id: str,
    channel: str,
    recipient_phone: str | None,
    recipient_email: str | None,
    message: str,
    idempotency_key: str,
    subject: str | None = None,
    html_body: str | None = None,
) -> bool:
    """
    Fire a single message to the channel gateway.

    Returns True on 202 Accepted, raises on unexpected errors.
    """
    payload = {
        "communication_id": communication_id,
        "campaign_id": campaign_id,
        "customer_id": customer_id,
        "channel": channel,
        "recipient_phone": recipient_phone,
        "recipient_email": recipient_email,
        "message": message,
        "subject": subject,
        "html_body": html_body,
        "idempotency_key": idempotency_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.CHANNEL_SERVICE_URL}/send",
            json=payload,
        )
        resp.raise_for_status()
        return resp.status_code == 202
