"""
Delivery event engine — the single place that records a real delivery event
(delivered / opened / clicked / failed) against a communication and rolls it
up to the campaign counters.

Used by:
  • routers/receipts.py    — delivered / failed callbacks from the channel gateway
  • routers/tracking.py     — opened / clicked / unsubscribe from real recipients

Events are deduplicated (each event type counts once per communication) and the
communication's headline status never regresses. When all sent messages are
resolved the campaign is finalized (AI post-mortem).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import supabase

logger = logging.getLogger(__name__)

STATUS_PRECEDENCE = {"queued": 0, "sent": 1, "delivered": 2, "opened": 3, "clicked": 4, "failed": 5}
_TIMESTAMP_FIELD = {"delivered": "delivered_at", "opened": "opened_at", "clicked": "clicked_at", "failed": "failed_at"}


def record_event(
    communication_id: str,
    status_value: str,
    *,
    timestamp: datetime | None = None,
    failure_reason: str | None = None,
) -> dict:
    """
    Record one delivery event. Returns a small result dict.
    Idempotent per (communication, status). Safe to call from anywhere.
    """
    if status_value not in _TIMESTAMP_FIELD:
        return {"ok": False, "reason": f"unsupported status: {status_value}"}

    ts = (timestamp or datetime.now(timezone.utc))
    ts_iso = ts.isoformat()

    comm_res = supabase.table("communications").select("*").eq("id", communication_id).execute()
    if not comm_res.data:
        return {"ok": False, "reason": "communication not found"}
    comm = comm_res.data[0]
    campaign_id = comm["campaign_id"]
    ts_field = _TIMESTAMP_FIELD[status_value]

    # Dedup: this event type already recorded for this communication.
    if comm.get(ts_field) is not None:
        return {"ok": True, "duplicate": True}

    # A click implies an open — backfill the open first if it never registered
    # (image blocking is common, so clicks often arrive without a pixel hit).
    if status_value == "clicked" and comm.get("opened_at") is None:
        record_event(communication_id, "opened", timestamp=ts)
        comm = supabase.table("communications").select("*").eq("id", communication_id).execute().data[0]

    new_status = comm["status"]
    if STATUS_PRECEDENCE.get(status_value, 0) > STATUS_PRECEDENCE.get(new_status, 0):
        new_status = status_value

    update = {"status": new_status, ts_field: ts_iso}
    if status_value == "failed" and failure_reason:
        update["failure_reason"] = failure_reason
    supabase.table("communications").update(update).eq("id", communication_id).execute()

    # Roll up to the campaign counter atomically.
    supabase.rpc("increment_campaign_counter", {
        "camp_id": campaign_id,
        "counter_name": f"total_{status_value}",
    }).execute()

    _maybe_finalize(campaign_id)
    return {"ok": True, "status": new_status}


def _maybe_finalize(campaign_id: str) -> None:
    """Finalize + trigger AI post-mortem once every sent message is resolved."""
    camp = (
        supabase.table("campaigns")
        .select("status, total_sent, total_delivered, total_failed")
        .eq("id", campaign_id)
        .execute()
    )
    if not camp.data:
        return
    c = camp.data[0]
    sent = c.get("total_sent", 0) or 0
    resolved = (c.get("total_delivered", 0) or 0) + (c.get("total_failed", 0) or 0)
    if sent > 0 and resolved >= sent and c["status"] == "running":
        # Flip to completed first to prevent a double trigger.
        supabase.table("campaigns").update({"status": "completed"}).eq("id", campaign_id).execute()
        try:
            from tasks.campaigns import finalize_campaign
            finalize_campaign.delay(campaign_id)
        except Exception as e:  # broker down — finalize inline as a fallback
            logger.warning("finalize enqueue failed (%s); running inline", e)
            try:
                from tasks.campaigns import finalize_campaign
                finalize_campaign.run(campaign_id)
            except Exception as e2:
                logger.error("inline finalize failed: %s", e2)
