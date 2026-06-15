"""
CRM router — Real engagement tracking (public, hit by recipients).

  GET /track/open/{comm_id}.gif        — open pixel  -> records a real open
  GET /track/click/{comm_id}           — click proxy -> records a click, 302 redirect
  GET /track/unsubscribe/{comm_id}     — one-click unsubscribe -> opt the customer out

These are the genuine engagement signals that replace the old simulator: an
"open" is recorded only when a recipient's mail client loads the pixel; a
"click" only when they actually click the CTA. Everything rolls up live to the
campaign counters via services.delivery_events.record_event.
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from config import supabase
from services.delivery_events import record_event

logger = logging.getLogger(__name__)

router = APIRouter()

# 1x1 transparent GIF
_PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


@router.get("/track/open/{comm_id}.gif")
async def track_open(comm_id: UUID):
    """Record an email open and return a 1x1 transparent pixel."""
    try:
        record_event(str(comm_id), "opened")
    except Exception as e:
        logger.warning(f"open tracking failed for {comm_id}: {e}")
    return Response(
        content=_PIXEL,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, private", "Pragma": "no-cache"},
    )


@router.get("/track/click/{comm_id}")
async def track_click(comm_id: UUID, u: str = Query(..., description="destination URL (encoded)")):
    """Record a click and redirect the recipient to the real destination."""
    try:
        record_event(str(comm_id), "clicked")
    except Exception as e:
        logger.warning(f"click tracking failed for {comm_id}: {e}")
    dest = unquote(u)
    if not dest.startswith(("http://", "https://")):
        dest = "https://" + dest
    return RedirectResponse(url=dest, status_code=302)


@router.get("/track/unsubscribe/{comm_id}", response_class=HTMLResponse)
async def track_unsubscribe(comm_id: UUID):
    """One-click unsubscribe — opt the recipient out of future email."""
    opted = False
    try:
        comm = supabase.table("communications").select("customer_id").eq("id", str(comm_id)).execute()
        if comm.data:
            supabase.table("customers").update({"email_opt_out": True}).eq(
                "id", comm.data[0]["customer_id"]
            ).execute()
            opted = True
    except Exception as e:
        logger.error(f"unsubscribe failed for {comm_id}: {e}")

    msg = (
        "You've been unsubscribed. You will no longer receive marketing emails."
        if opted else
        "We couldn't process your request, but it has been noted."
    )
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>Unsubscribed</title></head>
        <body style="font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
        display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
        <div style="text-align:center;max-width:420px;padding:32px">
        <div style="font-size:40px">✓</div>
        <h2 style="margin:12px 0">Unsubscribed</h2>
        <p style="color:#94a3b8;line-height:1.5">{msg}</p>
        </div></body></html>"""
    )
