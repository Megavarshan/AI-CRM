"""
CRM router — PDF Reports.

  GET /reports/{report_type}.pdf  — download a PDF report
       report_type ∈ customer | campaign | engagement | executive
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from deps import OrgContext, get_org
from services.report_builder import REPORT_TITLES, build_report

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/reports/{report_type}.pdf")
async def download_report(report_type: str, org: OrgContext = Depends(get_org)):
    """Generate and stream a PDF business report."""
    if report_type not in REPORT_TITLES:
        raise HTTPException(status_code=404, detail=f"Unknown report type '{report_type}'.")
    try:
        pdf_bytes = build_report(report_type, org.org_id)
    except Exception as e:
        logger.error(f"Report generation failed ({report_type}): {e}")
        raise HTTPException(status_code=500, detail=str(e))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"orbit_{report_type}_report_{stamp}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
