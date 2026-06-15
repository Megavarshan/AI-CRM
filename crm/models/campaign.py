"""Pydantic models for Campaign domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str
    segment_id: UUID
    channel: str = Field(..., pattern=r"^(whatsapp|sms|email|rcs)$")
    message_template: str
    personalized: bool = True
    cta_url: Optional[str] = None        # click-tracked destination (email); defaults to org website
    scheduled_at: Optional[datetime] = None


class CampaignRead(BaseModel):
    id: UUID
    name: str
    segment_id: UUID
    channel: str
    message_template: str
    personalized: bool
    status: str   # draft | scheduled | running | completed | failed
    scheduled_at: Optional[datetime] = None
    launched_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_failed: int
    ai_postmortem: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CampaignStats(BaseModel):
    campaign_id: UUID
    name: str
    status: str
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_failed: int
    delivery_rate: float
    open_rate: float
    click_rate: float
    channel_breakdown: dict
    ai_postmortem: Optional[str] = None
