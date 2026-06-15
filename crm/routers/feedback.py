"""
CRM router — Campaign Feedback (Human-in-the-Loop learning).

Endpoints:
  POST /feedback                       — submit feedback for a completed campaign
  GET  /campaigns/{id}/feedback        — feedback for a campaign
  GET  /org/preferences                — the org's learned AI preference profile
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from config import supabase
from deps import OrgContext, get_org
from services import org_learning

logger = logging.getLogger(__name__)

router = APIRouter()


class FeedbackCreate(BaseModel):
    campaign_id: UUID
    rating: int = Field(..., ge=1, le=5)
    business_impact: Optional[str] = None   # high_sales | some_sales | no_impact | negative
    comments: Optional[str] = None


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(body: FeedbackCreate, org: OrgContext = Depends(get_org)):
    """Record feedback for a completed campaign and refresh learned preferences."""
    org_id = org.require_org()

    # Verify the campaign belongs to this org
    camp = org.scope(
        supabase.table("campaigns").select("id, status").eq("id", str(body.campaign_id))
    ).execute()
    if not camp.data:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    payload = {
        "org_id": org_id,
        "campaign_id": str(body.campaign_id),
        "rating": body.rating,
        "business_impact": body.business_impact,
        "comments": body.comments,
        "submitted_by": org_id,
    }
    try:
        res = supabase.table("campaign_feedback").insert(payload).execute()
    except Exception as e:
        if "campaign_feedback" in str(e) and ("PGRST205" in str(e) or "schema cache" in str(e)):
            raise HTTPException(
                status_code=503,
                detail="The campaign_feedback table is missing. Run crm/db/migrations/003_multi_tenancy.sql.",
            )
        raise HTTPException(status_code=500, detail=str(e))

    # New feedback changes the org's learned profile
    org_learning.invalidate(org_id)
    prefs = org_learning.compute_preferences(org_id)

    return {
        "feedback": res.data[0] if res.data else payload,
        "updated_preferences": prefs,
        "message": "Thanks! Future AI campaigns will adapt to this feedback.",
    }


@router.get("/campaigns/{campaign_id}/feedback")
async def list_campaign_feedback(campaign_id: UUID, org: OrgContext = Depends(get_org)):
    """Return all feedback submitted for a campaign."""
    res = org.scope(
        supabase.table("campaign_feedback").select("*").eq("campaign_id", str(campaign_id))
    ).order("created_at", desc=True).execute()
    return res.data or []


@router.get("/org/preferences")
async def get_org_preferences(org: OrgContext = Depends(get_org)):
    """Return the organization's learned AI preference profile."""
    org_id = org.require_org()
    return org_learning.compute_preferences(org_id)
