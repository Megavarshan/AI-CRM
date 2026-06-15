"""Pydantic models for Communication domain (individual messages)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CommunicationCreate(BaseModel):
    campaign_id: UUID
    customer_id: UUID
    channel: str
    personalized_message: str
    idempotency_key: str


class CommunicationRead(BaseModel):
    id: UUID
    campaign_id: UUID
    customer_id: UUID
    channel: str
    personalized_message: str
    status: str   # queued | sent | delivered | failed | opened | clicked
    idempotency_key: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime


class ReceiptCallback(BaseModel):
    communication_id: UUID
    campaign_id: UUID
    idempotency_key: str
    status: str   # delivered | failed | opened | clicked
    timestamp: datetime
