"""Pydantic models for Customer domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Nested score ──────────────────────────────────────────────────────────────

class CustomerScore(BaseModel):
    recency_days: Optional[int] = None
    frequency: Optional[int] = None
    monetary: Optional[float] = None
    rfm_score: Optional[float] = None
    churn_risk: Optional[str] = None   # low | medium | high | critical
    top_category: Optional[str] = None
    last_product: Optional[str] = None
    scored_at: Optional[datetime] = None


# ── Request / Response schemas ────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: Optional[str] = None
    phone: Optional[str] = Field(None, pattern=r"^\+[1-9]\d{6,14}$")
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    channel_pref: str = Field("whatsapp", pattern=r"^(whatsapp|sms|email|rcs)$")
    external_id: Optional[str] = None


class CustomerRead(BaseModel):
    id: UUID
    external_id: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    channel_pref: str
    created_at: datetime
    updated_at: datetime
    score: Optional[CustomerScore] = None


from models.order import OrderRead  # noqa: E402
from models.campaign import CampaignRead  # noqa: E402

class CustomerDetailedRead(CustomerRead):
    orders: list[OrderRead] = []
    campaigns: list[CampaignRead] = []
    ai_summary: Optional[str] = None


class CustomerListResponse(BaseModel):
    data: list[CustomerRead]
    total: int
    page: int
    limit: int


class ImportResponse(BaseModel):
    import_id: str
    rows_total: int
    rows_imported: int
    rows_failed: int
    status: str
    errors: list[dict] = []
