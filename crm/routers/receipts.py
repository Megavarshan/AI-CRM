"""
CRM router — Receipts.

POST /receipts  — delivery/failure callback from the channel gateway.

This is the inbound side of the two-service loop. The actual bookkeeping lives
in services/delivery_events.record_event (shared with the tracking endpoints).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from models.communication import ReceiptCallback
from services.delivery_events import record_event

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/receipts", status_code=status.HTTP_200_OK)
async def ingest_receipt(body: ReceiptCallback):
    """Process a delivered/failed callback from the channel gateway."""
    try:
        result = record_event(
            str(body.communication_id),
            body.status,
            timestamp=body.timestamp,
        )
        if not result.get("ok"):
            # Unknown comm or bad status — 404/400 as appropriate
            if result.get("reason") == "communication not found":
                raise HTTPException(status_code=404, detail="Communication record not found.")
            raise HTTPException(status_code=400, detail=result.get("reason", "bad event"))
        return {"status": "duplicate" if result.get("duplicate") else "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting receipt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
