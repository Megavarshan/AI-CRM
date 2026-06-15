"""
CRM router — Marketing Strategist Agent.

Endpoints:
  GET /strategist/analysis      — opportunities + recommended campaign + forecast
  GET /strategist/weekly-report — narrative weekly strategic report
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from deps import OrgContext, get_org
from services import strategist as strategist_svc

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/strategist/analysis")
async def strategist_analysis(org: OrgContext = Depends(get_org)):
    """Proactive strategic analysis: opportunities, recommendation, forecast."""
    try:
        return strategist_svc.generate_strategy(org.org_id)
    except Exception as e:
        logger.error(f"Strategist analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategist/weekly-report")
async def strategist_weekly_report(org: OrgContext = Depends(get_org)):
    """Generate the narrative weekly strategic report."""
    try:
        return strategist_svc.generate_weekly_report(org.org_id)
    except Exception as e:
        logger.error(f"Weekly report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
