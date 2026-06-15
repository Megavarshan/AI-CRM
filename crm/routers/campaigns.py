"""
CRM router — Campaigns.

Endpoints:
  GET  /campaigns            — list campaigns (filterable by status)
  POST /campaigns            — create draft campaign
  POST /campaigns/{id}/launch — launch a campaign
  GET  /campaigns/{id}/stats  — live delivery stats
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from config import supabase
from deps import OrgContext, get_org
from models.campaign import CampaignCreate, CampaignRead, CampaignStats

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/campaigns", response_model=list[CampaignRead])
async def list_campaigns(
    campaign_status: str = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    org: OrgContext = Depends(get_org),
):
    """Return campaigns ordered by created_at descending."""
    start = (page - 1) * limit
    end = start + limit - 1

    try:
        query = org.scope(supabase.table("campaigns").select("*"))
        if campaign_status:
            query = query.eq("status", campaign_status)
        
        res = query.order("created_at", desc=True).range(start, end).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")


@router.post("/campaigns", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(body: CampaignCreate, org: OrgContext = Depends(get_org)):
    """Create a campaign in draft status."""
    # mode="json" serialises UUID -> str and datetime -> ISO string so the
    # payload is JSON-safe for supabase-py.
    payload = org.stamp(body.model_dump(mode="json"))
    payload["status"] = "draft"
    payload["total_sent"] = 0
    payload["total_delivered"] = 0
    payload["total_opened"] = 0
    payload["total_clicked"] = 0
    payload["total_failed"] = 0

    try:
        # Validate segment exists in this org before proceeding
        seg_res = org.scope(
            supabase.table("segments").select("id").eq("id", str(body.segment_id))
        ).execute()
        if not seg_res.data:
            raise HTTPException(
                status_code=400,
                detail=f"Segment with ID '{body.segment_id}' does not exist.",
            )

        res = supabase.table("campaigns").insert(payload).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Database insert returned empty result.")
        
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{campaign_id}/launch", status_code=status.HTTP_202_ACCEPTED)
async def launch_campaign(campaign_id: UUID, org: OrgContext = Depends(get_org)):
    """Launch a campaign asynchronously using Celery."""
    try:
        res = org.scope(
            supabase.table("campaigns").select("*").eq("id", str(campaign_id))
        ).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Campaign not found.")
        
        campaign = res.data[0]
        if campaign["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail=f"Campaign is in '{campaign['status']}' state. Only 'draft' campaigns can be launched.",
            )

        # Mark campaign as running initially
        supabase.table("campaigns").update({
            "status": "running",
            "launched_at": "now()",
        }).eq("id", str(campaign_id)).execute()

        # Enqueue the launch process in Celery
        from tasks.campaigns import launch_campaign_task
        launch_campaign_task.delay(str(campaign_id))

        return {
            "campaign_id": str(campaign_id),
            "status": "running",
            "message": "Campaign launch successfully scheduled.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error launching campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{campaign_id}/analyze")
async def analyze_campaign(campaign_id: UUID, org: OrgContext = Depends(get_org)):
    """Generate/refresh the AI post-mortem from the campaign's current live engagement."""
    res = org.scope(
        supabase.table("campaigns").select("id").eq("id", str(campaign_id))
    ).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    try:
        from tasks.campaigns import generate_campaign_analysis
        postmortem = generate_campaign_analysis(str(campaign_id))
        return {"campaign_id": str(campaign_id), "ai_postmortem": postmortem}
    except Exception as e:
        logger.error(f"Analysis generation failed for {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}/stats", response_model=CampaignStats)
async def get_campaign_stats(campaign_id: UUID, org: OrgContext = Depends(get_org)):
    """Return live delivery stats for a campaign."""
    try:
        res = org.scope(
            supabase.table("campaigns").select("*").eq("id", str(campaign_id))
        ).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Campaign not found.")
        
        campaign = res.data[0]
        
        sent = campaign.get("total_sent", 0)
        delivered = campaign.get("total_delivered", 0)
        opened = campaign.get("total_opened", 0)
        clicked = campaign.get("total_clicked", 0)
        failed = campaign.get("total_failed", 0)

        delivery_rate = round((delivered / sent) * 100, 1) if sent > 0 else 0.0
        open_rate = round((opened / delivered) * 100, 1) if delivered > 0 else 0.0
        click_rate = round((clicked / opened) * 100, 1) if opened > 0 else 0.0

        channel_breakdown = {
            campaign["channel"]: {
                "sent": sent,
                "delivered": delivered,
                "opened": opened,
                "clicked": clicked,
                "failed": failed,
            }
        }

        return {
            "campaign_id": campaign["id"],
            "name": campaign["name"],
            "status": campaign["status"],
            "total_sent": sent,
            "total_delivered": delivered,
            "total_opened": opened,
            "total_clicked": clicked,
            "total_failed": failed,
            "delivery_rate": delivery_rate,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "channel_breakdown": channel_breakdown,
            "ai_postmortem": campaign.get("ai_postmortem"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching stats for campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
