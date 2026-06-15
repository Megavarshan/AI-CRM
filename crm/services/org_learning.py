"""
Org Learning Layer — derives an organization's learned preferences from its
campaign feedback + campaign history, and renders them as a prompt snippet that
is injected into AI message generation (personalization, draft_message).

This is the Human-in-the-Loop mechanism: as an org rates campaigns, future
AI-generated campaigns adapt to what worked for that org.
"""

from __future__ import annotations

import logging
from typing import Optional

from config import supabase

logger = logging.getLogger(__name__)

# Simple in-process cache (org_id -> (snippet, prefs)). Rebuilt on new feedback.
_cache: dict[str, dict] = {}


def invalidate(org_id: str) -> None:
    _cache.pop(org_id, None)


def compute_preferences(org_id: str) -> dict:
    """
    Aggregate feedback + the campaigns it refers to into a preference profile:
      best_channels, preferred_tone hints, discount_sensitivity, avg_rating, etc.
    """
    fb_res = (
        supabase.table("campaign_feedback")
        .select("rating, business_impact, comments, campaign_id")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    feedback = fb_res.data or []
    if not feedback:
        return {"has_feedback": False}

    campaign_ids = [f["campaign_id"] for f in feedback if f.get("campaign_id")]
    camp_map: dict[str, dict] = {}
    if campaign_ids:
        camp_res = (
            supabase.table("campaigns")
            .select("id, channel, personalized, total_opened, total_delivered")
            .in_("id", campaign_ids)
            .execute()
        )
        camp_map = {c["id"]: c for c in (camp_res.data or [])}

    ratings = [f["rating"] for f in feedback if f.get("rating") is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    # Channel performance weighted by rating
    channel_score: dict[str, float] = {}
    channel_count: dict[str, int] = {}
    positive_comments: list[str] = []
    impact_counts: dict[str, int] = {}

    for f in feedback:
        camp = camp_map.get(f.get("campaign_id"))
        rating = f.get("rating") or 3
        impact = f.get("business_impact")
        if impact:
            impact_counts[impact] = impact_counts.get(impact, 0) + 1
        if camp:
            ch = camp.get("channel")
            if ch:
                channel_score[ch] = channel_score.get(ch, 0) + rating
                channel_count[ch] = channel_count.get(ch, 0) + 1
        if rating >= 4 and f.get("comments"):
            positive_comments.append(f["comments"].strip())

    best_channels = sorted(
        ({"channel": ch, "avg_rating": round(channel_score[ch] / channel_count[ch], 2)}
         for ch in channel_score),
        key=lambda x: x["avg_rating"], reverse=True,
    )

    # Discount sensitivity heuristic: positive feedback mentioning discounts/offers
    discount_mentions = sum(
        1 for c in positive_comments
        if any(w in c.lower() for w in ("discount", "offer", "%", "sale", "deal", "off"))
    )
    discount_sensitivity = (
        "high" if discount_mentions >= 2 else "medium" if discount_mentions == 1 else "low"
    )

    return {
        "has_feedback": True,
        "feedback_count": len(feedback),
        "avg_rating": avg_rating,
        "best_channels": best_channels,
        "impact_breakdown": impact_counts,
        "discount_sensitivity": discount_sensitivity,
        "positive_notes": positive_comments[:5],
    }


def preference_snippet(org_id: Optional[str]) -> str:
    """
    A short instruction block injected into AI generation prompts so messages
    adapt to the org's accumulated feedback. Empty string if no org / no data.
    """
    if not org_id:
        return ""
    if org_id in _cache:
        return _cache[org_id]["snippet"]

    try:
        prefs = compute_preferences(org_id)
    except Exception as e:
        logger.warning(f"Could not compute org preferences for {org_id}: {e}")
        return ""

    if not prefs.get("has_feedback"):
        _cache[org_id] = {"snippet": "", "prefs": prefs}
        return ""

    lines = ["LEARNED BRAND PREFERENCES (from this org's past campaign feedback — honour these):"]
    if prefs.get("best_channels"):
        top = prefs["best_channels"][0]
        lines.append(f"- This brand's audience responds best on {top['channel']} (avg rating {top['avg_rating']}/5).")
    if prefs.get("discount_sensitivity") == "high":
        lines.append("- Discounts/offers consistently land well — lead with a clear offer.")
    elif prefs.get("discount_sensitivity") == "low":
        lines.append("- Avoid leaning on discounts; emphasise value, story, and relevance instead.")
    for note in prefs.get("positive_notes", [])[:3]:
        lines.append(f'- Past positive feedback: "{note}"')
    if prefs.get("avg_rating") is not None:
        lines.append(f"- Overall the brand rates AI campaigns {prefs['avg_rating']}/5 — keep improving on that.")

    snippet = "\n".join(lines)
    _cache[org_id] = {"snippet": snippet, "prefs": prefs}
    return snippet
