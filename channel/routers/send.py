"""
Channel Service router — POST /send.

Accepts a message payload, returns 202 immediately, and enqueues the REAL
delivery task (SMTP email / Twilio SMS-WhatsApp).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from tasks.deliver import deliver_message

router = APIRouter()


class SendPayload(BaseModel):
    communication_id: str
    campaign_id: str
    customer_id: str
    channel: str
    recipient_phone: str | None = None
    recipient_email: str | None = None
    subject: str | None = None
    message: str | None = None       # plain-text body (sms/whatsapp, email fallback)
    html_body: str | None = None     # rendered HTML (email)
    idempotency_key: str


@router.post("/send", status_code=202)
async def send_message(payload: SendPayload):
    """Accept a message for real delivery; processing happens asynchronously."""
    deliver_message.delay(payload.model_dump())
    return {"accepted": True, "communication_id": payload.communication_id}
