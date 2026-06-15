"""
Celery tasks for campaign orchestration.

Tasks:
  launch_campaign_task(campaign_id) - pulls segment, personalize/format messages, sends to channel, updates status
  finalize_campaign(campaign_id)     - sets campaign to completed and triggers AI postmortem generation
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
import pandas as pd

from celery_app import app
from config import supabase
from services.ai_engine import generate_personalized_messages, generate_postmortem
from services.segment_executor import get_segment_customer_ids

logger = logging.getLogger(__name__)


@app.task(name="tasks.campaigns.launch_campaign_task", bind=True, max_retries=3)
def launch_campaign_task(self, campaign_id: str) -> None:
    """Orchestrates campaign launch in the background."""
    try:
        logger.info(f"Starting launch for campaign {campaign_id}")
        
        # 1. Fetch Campaign
        camp_res = supabase.table("campaigns").select("*").eq("id", campaign_id).execute()
        if not camp_res.data:
            logger.error(f"Campaign {campaign_id} not found.")
            return
        campaign = camp_res.data[0]

        # 2. Fetch Segment
        seg_res = supabase.table("segments").select("*").eq("id", campaign["segment_id"]).execute()
        if not seg_res.data:
            logger.error(f"Segment {campaign['segment_id']} not found for campaign.")
            supabase.table("campaigns").update({
                "status": "failed",
                "ai_postmortem": "Launch failed: Segment not found."
            }).eq("id", campaign_id).execute()
            return
        segment = seg_res.data[0]
        org_id = campaign.get("org_id")
        channel = campaign["channel"]

        # Resolve brand name + CTA destination (click-tracked) from the org.
        brand_name = "Our Store"
        cta_url = campaign.get("cta_url")
        if org_id:
            org_row = supabase.table("organizations").select("company_name, website").eq("id", org_id).execute()
            if org_row.data:
                brand_name = org_row.data[0].get("company_name") or brand_name
                cta_url = cta_url or org_row.data[0].get("website")
        cta_url = cta_url or "https://example.com"

        # 3. Resolve Customer IDs (scoped to the campaign's organization)
        customer_ids = get_segment_customer_ids(segment["filter_spec"], org_id)
        if not customer_ids:
            logger.info(f"Segment has 0 matching customers. Completing campaign {campaign_id} immediately.")
            supabase.table("campaigns").update({
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "total_sent": 0,
                "ai_postmortem": "Campaign completed with 0 recipients in segment."
            }).eq("id", campaign_id).execute()
            return

        # 4. Fetch Customer Details + Scores in chunks of 100
        customers = []
        chunk_size = 100
        for i in range(0, len(customer_ids), chunk_size):
            chunk_ids = customer_ids[i : i + chunk_size]
            cust_res = (
                supabase.table("customers")
                .select("*, score:customer_scores(*)")
                .in_("id", chunk_ids)
                .execute()
            )
            for row in (cust_res.data or []):
                score_val = row.get("score")
                if isinstance(score_val, list):
                    score_val = score_val[0] if score_val else None
                row["last_product"] = score_val.get("last_product") if score_val else None
                row["top_category"] = score_val.get("top_category") if score_val else None
                row["recency_days"] = score_val.get("recency_days") if score_val else 0
                customers.append(row)

        # 4b. Channel-specific reachability filter (real sending — no fake recipients).
        skipped = 0
        if channel == "email":
            kept = [c for c in customers if c.get("email") and not c.get("email_opt_out")]
            skipped = len(customers) - len(kept)
            customers = kept
        elif channel in ("sms", "whatsapp", "rcs"):
            kept = [c for c in customers if c.get("phone")]
            skipped = len(customers) - len(kept)
            customers = kept

        if not customers:
            logger.warning(f"No reachable recipients for campaign {campaign_id} on {channel}.")
            supabase.table("campaigns").update({
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "total_sent": 0,
                "ai_postmortem": f"No reachable recipients on {channel} (missing contact info or opted out).",
            }).eq("id", campaign_id).execute()
            return

        # Email needs a subject line (one per campaign, AI-written).
        subject = None
        if channel == "email":
            from services.ai_engine import generate_email_subject
            subject = generate_email_subject(campaign["name"], campaign["message_template"], brand_name)

        # 5. Generate Messages (Personalized via AI vs static template formatting)
        messages = []
        if campaign["personalized"]:
            logger.info(f"Calling LLM for personalized messages for {len(customers)} customers...")
            campaign_brief = f"Campaign name: {campaign['name']}. Base Template: {campaign['message_template']}"
            messages = generate_personalized_messages(customers, campaign_brief, channel, org_id)
        else:
            logger.info(f"Formatting static message template for {len(customers)} customers...")
            for c in customers:
                msg = campaign["message_template"]
                msg = msg.replace("{first_name}", c["first_name"])
                msg = msg.replace("{city}", c.get("city") or "your city")
                msg = msg.replace("{last_product}", c.get("last_product") or "our products")
                msg = msg.replace("{top_category}", c.get("top_category") or "skincare")
                messages.append(msg)

        # 6. Bulk Insert Communications in status 'queued'
        comm_records = []
        for c, msg in zip(customers, messages):
            comm_records.append({
                "campaign_id": campaign_id,
                "customer_id": c["id"],
                "org_id": org_id,
                "channel": channel,
                "personalized_message": msg,
                "subject": subject,
                "status": "queued",
                "idempotency_key": f"{campaign_id}_{c['id']}_attempt_1"
            })

        inserted_comms = []
        for i in range(0, len(comm_records), chunk_size):
            chunk = comm_records[i : i + chunk_size]
            ins_res = supabase.table("communications").insert(chunk).execute()
            if ins_res.data:
                inserted_comms.extend(ins_res.data)

        # Map customer back + render the per-recipient HTML email (needs the
        # communication id for tracking, which only exists after insert).
        from services.email_templates import render_email
        id_to_cust = {c["id"]: c for c in customers}
        cta_label = "Shop Now" if channel == "email" else ""
        for comm in inserted_comms:
            cust = id_to_cust.get(comm["customer_id"])
            if not cust:
                continue
            comm["phone"] = cust.get("phone")
            comm["email"] = cust.get("email")
            if channel == "email":
                comm["html_body"] = render_email(
                    comm_id=str(comm["id"]),
                    brand_name=brand_name,
                    first_name=cust.get("first_name") or "",
                    body_text=comm["personalized_message"],
                    cta_label=cta_label,
                    cta_url=cta_url,
                )

        # 7. Concurrently send messages to channel-service
        logger.info(f"Sending {len(inserted_comms)} messages to channel service...")
        send_results = asyncio.run(send_all_messages_with_limit(inserted_comms))

        # 8. Update Communications status (sent / failed).
        # NOTE: we use UPDATE (not upsert) here. communications has NOT NULL
        # columns (campaign_id, customer_id, ...) and Postgres enforces NOT NULL
        # *before* ON CONFLICT, so a partial upsert would raise 23502.
        now_str = datetime.now(timezone.utc).isoformat()
        sent_ids = [comm_id for comm_id, success, _ in send_results if success]
        failed = [(comm_id, err_msg) for comm_id, success, err_msg in send_results if not success]
        total_sent = len(sent_ids)
        total_failed = len(failed)

        # Bulk-update the successful sends in chunks.
        for i in range(0, len(sent_ids), chunk_size):
            chunk_ids = sent_ids[i : i + chunk_size]
            supabase.table("communications").update({
                "status": "sent",
                "sent_at": now_str,
            }).in_("id", chunk_ids).execute()

        # Failed sends carry a per-row reason, so update individually (rare path).
        for comm_id, err_msg in failed:
            supabase.table("communications").update({
                "status": "failed",
                "failed_at": now_str,
                "failure_reason": err_msg,
            }).eq("id", comm_id).execute()

        # 9. Update Campaign Status to 'running'
        supabase.table("campaigns").update({
            "status": "running",
            "total_sent": total_sent,
            "total_failed": total_failed,
        }).eq("id", campaign_id).execute()

        logger.info(f"Campaign {campaign_id} is running. Sent: {total_sent}, Failed: {total_failed}.")

    except Exception as exc:
        logger.error(f"Error launching campaign: {exc}")
        # Mark campaign as failed
        supabase.table("campaigns").update({
            "status": "failed",
            "ai_postmortem": f"Launch execution error: {exc}"
        }).eq("id", campaign_id).execute()
        raise self.retry(exc=exc, countdown=30)


async def send_all_messages_with_limit(communications: list[dict], max_concurrent: int = 20) -> list[tuple[str, bool, str | None]]:
    """Fire messages to channel service concurrently, limiting socket overload."""
    from services.campaign_sender import send_message
    sem = asyncio.Semaphore(max_concurrent)
    
    async def send_one(comm: dict) -> tuple[str, bool, str | None]:
        async with sem:
            try:
                success = await send_message(
                    communication_id=str(comm["id"]),
                    campaign_id=str(comm["campaign_id"]),
                    customer_id=str(comm["customer_id"]),
                    channel=comm["channel"],
                    recipient_phone=comm.get("phone"),
                    recipient_email=comm.get("email"),
                    message=comm["personalized_message"],
                    idempotency_key=comm["idempotency_key"],
                    subject=comm.get("subject"),
                    html_body=comm.get("html_body"),
                )
                return comm["id"], success, None
            except Exception as e:
                logger.error(f"Error sending communication {comm['id']}: {e}")
                return comm["id"], False, str(e)

    tasks = [send_one(c) for c in communications]
    return await asyncio.gather(*tasks)


@app.task(name="tasks.campaigns.finalize_campaign", bind=True, max_retries=3)
def finalize_campaign(self, campaign_id: str) -> None:
    """
    Mark a campaign completed once every message is delivered/failed.

    NOTE: we deliberately do NOT write the AI post-mortem here. For real email,
    opens & clicks arrive minutes-to-days AFTER delivery, so a post-mortem at
    delivery-time would always read 0% engagement. The analysis is generated
    on demand from live stats via generate_campaign_analysis (see analyze
    endpoint), so it always reflects real, accumulated engagement.
    """
    try:
        logger.info(f"Finalizing (delivery complete) campaign {campaign_id}...")
        supabase.table("campaigns").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", campaign_id).execute()
        logger.info(f"Campaign {campaign_id} delivery complete.")

    except Exception as exc:
        logger.error(f"Error finalising campaign {campaign_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


def generate_campaign_analysis(campaign_id: str) -> str:
    """
    Generate (and store) the AI post-mortem from the campaign's CURRENT live
    stats. Called on demand so it always reflects real accumulated engagement.
    """
    camp_res = supabase.table("campaigns").select("*").eq("id", campaign_id).execute()
    if not camp_res.data:
        raise ValueError("Campaign not found")
    campaign = camp_res.data[0]

    seg_res = supabase.table("segments").select("*").eq("id", campaign["segment_id"]).execute()
    segment = seg_res.data[0] if seg_res.data else {"name": "Unknown"}

    sent = campaign.get("total_sent", 0) or 0
    delivered = campaign.get("total_delivered", 0) or 0
    opened = campaign.get("total_opened", 0) or 0
    clicked = campaign.get("total_clicked", 0) or 0
    failed = campaign.get("total_failed", 0) or 0
    stats = {
        "total_sent": sent,
        "delivery_rate": (delivered / sent) * 100 if sent else 0.0,
        "open_rate": (opened / delivered) * 100 if delivered else 0.0,
        "click_rate": (clicked / opened) * 100 if opened else 0.0,
        "total_failed": failed,
    }

    postmortem = generate_postmortem(campaign, stats, segment)
    supabase.table("campaigns").update({"ai_postmortem": postmortem}).eq("id", campaign_id).execute()
    return postmortem
