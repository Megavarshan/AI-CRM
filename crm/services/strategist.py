"""
Marketing Strategist Agent — proactive strategic analysis for an organization.

Unlike the Copilot (which executes user requests), the Strategist analyses the
org's data to surface opportunities, recommend campaign strategy, forecast
revenue impact, and produce a weekly strategic report. All org-scoped.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from config import settings, supabase

logger = logging.getLogger(__name__)


def _org(query, org_id: Optional[str]):
    return query.eq("org_id", org_id) if org_id else query


def _groq():
    from services.ai_engine import _get_groq_client
    return _get_groq_client()


# ── Data gathering ────────────────────────────────────────────────────────────

def gather_org_signals(org_id: Optional[str]) -> dict:
    """Pull the raw signals the strategist reasons over (all org-scoped)."""
    scores = _fetch_all_scores(org_id)
    total_customers = len(scores)

    churn = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    dormant_high_value: list[dict] = []
    monetary_values: list[float] = []
    for s in scores:
        cr = s.get("churn_risk")
        if cr in churn:
            churn[cr] += 1
        mon = float(s.get("monetary") or 0)
        monetary_values.append(mon)
        rec = s.get("recency_days") or 0
        # High value + dormant = prime win-back target
        if mon >= 8000 and rec >= 60:
            dormant_high_value.append({
                "monetary": round(mon, 2),
                "recency_days": rec,
                "top_category": s.get("top_category"),
                "churn_risk": cr,
            })

    dormant_high_value.sort(key=lambda x: x["monetary"], reverse=True)
    avg_ltv = round(sum(monetary_values) / len(monetary_values), 2) if monetary_values else 0
    at_risk_value = round(
        sum(float(s.get("monetary") or 0) for s in scores
            if s.get("churn_risk") in ("high", "critical")), 2
    )

    # Campaign performance to date
    camps = _org(
        supabase.table("campaigns").select(
            "name, channel, status, total_sent, total_delivered, total_opened, total_clicked"
        ), org_id,
    ).execute().data or []

    channel_perf: dict[str, dict] = {}
    for c in camps:
        ch = c.get("channel")
        if not ch:
            continue
        d = channel_perf.setdefault(ch, {"delivered": 0, "opened": 0, "clicked": 0})
        d["delivered"] += c.get("total_delivered", 0)
        d["opened"] += c.get("total_opened", 0)
        d["clicked"] += c.get("total_clicked", 0)
    for ch, d in channel_perf.items():
        d["open_rate"] = round((d["opened"] / d["delivered"]) * 100, 1) if d["delivered"] else 0.0
        d["click_rate"] = round((d["clicked"] / d["opened"]) * 100, 1) if d["opened"] else 0.0

    best_channel = max(
        channel_perf.items(), key=lambda kv: kv[1]["open_rate"], default=(None, {})
    )[0]

    return {
        "total_customers": total_customers,
        "churn_distribution": churn,
        "at_risk_customer_value": at_risk_value,
        "avg_lifetime_value": avg_ltv,
        "dormant_high_value_count": len(dormant_high_value),
        "dormant_high_value_examples": dormant_high_value[:10],
        "campaign_count": len(camps),
        "channel_performance": channel_perf,
        "best_channel": best_channel,
    }


def _fetch_all_scores(org_id: Optional[str]) -> list[dict]:
    out: list[dict] = []
    offset, chunk = 0, 1000
    while True:
        res = _org(
            supabase.table("customer_scores").select("monetary, recency_days, churn_risk, top_category, frequency"),
            org_id,
        ).range(offset, offset + chunk - 1).execute()
        if not res.data:
            break
        out.extend(res.data)
        if len(res.data) < chunk:
            break
        offset += chunk
    return out


# ── Revenue forecasting (heuristic) ──────────────────────────────────────────

def forecast_winback(signals: dict) -> dict:
    """
    Simple, explainable revenue forecast for a win-back campaign targeting
    the dormant high-value cohort.
    """
    n = signals["dormant_high_value_count"]
    examples = signals["dormant_high_value_examples"]
    avg_value = (
        round(sum(e["monetary"] for e in examples) / len(examples), 2) if examples else 0
    )
    best = signals.get("best_channel")
    # Expected reactivation rate scales with the channel's open rate (fallback 8%)
    open_rate = signals["channel_performance"].get(best, {}).get("open_rate", 25) if best else 25
    reactivation_rate = round(min(0.18, max(0.05, open_rate / 100 * 0.15)), 3)
    expected_reactivations = round(n * reactivation_rate)
    # Assume one repeat order at ~30% of historical LTV
    projected_revenue = round(expected_reactivations * avg_value * 0.30, 2)

    return {
        "target_customers": n,
        "recommended_channel": best or "whatsapp",
        "expected_reactivation_rate": f"{reactivation_rate * 100:.1f}%",
        "expected_reactivations": expected_reactivations,
        "projected_revenue": projected_revenue,
        "avg_cohort_ltv": avg_value,
    }


# ── LLM strategy synthesis ────────────────────────────────────────────────────

STRATEGIST_SYSTEM_PROMPT = """
You are the Marketing Strategist for a D2C brand using the Orbit CRM.
You are proactive and business-minded: you find opportunities and make concrete,
prioritised recommendations a marketer can act on this week.

You are given the brand's data signals as JSON. Produce a JSON object EXACTLY:
{
  "headline": "<one punchy sentence on the single biggest opportunity>",
  "opportunities": [
    {"title": "...", "why": "...", "potential": "high|medium|low"}
  ],
  "recommended_campaign": {
    "audience": "...", "channel": "whatsapp|sms|email|rcs",
    "message_style": "...", "offer_strategy": "...", "timing": "..."
  },
  "risks": ["..."],
  "recommendations": ["<3-5 concrete, prioritised actions>"]
}
Be specific and use the actual numbers. Return ONLY JSON, no markdown.
"""


def generate_strategy(org_id: Optional[str]) -> dict:
    """Gather signals, forecast, and synthesise a strategy via the LLM."""
    signals = gather_org_signals(org_id)
    forecast = forecast_winback(signals)

    if signals["total_customers"] == 0:
        return {
            "signals": signals,
            "forecast": forecast,
            "strategy": {
                "headline": "No customer data yet — import customers and orders to unlock strategy.",
                "opportunities": [],
                "recommended_campaign": {},
                "risks": ["No data to analyse."],
                "recommendations": ["Import your customer and order data from Settings → AI Data Ingestion."],
            },
        }

    # RAG: ground the strategy in real retrieved customer exemplars.
    retrieved = []
    try:
        from services.semantic import retrieve_context
        retrieved = retrieve_context("high-value customers who are lapsing and likely to churn", org_id, k=5)
    except Exception as e:
        logger.info(f"Strategist RAG retrieval skipped: {e}")

    user_prompt = (
        "Brand data signals:\n"
        + json.dumps(signals, default=str, indent=2)
        + "\n\nWin-back forecast:\n"
        + json.dumps(forecast, default=str, indent=2)
        + ("\n\nRetrieved real customer exemplars (use these to make the advice concrete):\n"
           + json.dumps(retrieved, default=str, indent=2) if retrieved else "")
    )
    try:
        resp = _groq().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": STRATEGIST_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=1200,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        strategy = json.loads(raw)
    except Exception as e:
        logger.error(f"Strategist LLM failed: {e}")
        strategy = {
            "headline": f"{signals['dormant_high_value_count']} high-value customers have gone dormant — launch a win-back.",
            "opportunities": [],
            "recommended_campaign": {},
            "risks": [],
            "recommendations": ["Review the forecast and launch a win-back campaign for dormant high-value customers."],
        }

    return {"signals": signals, "forecast": forecast, "strategy": strategy}


# ── Weekly report ─────────────────────────────────────────────────────────────

WEEKLY_REPORT_PROMPT = """
You are the Marketing Strategist. Write a concise weekly strategic report (4-6 short
paragraphs) for the brand's administrator, based on the signals and strategy JSON.
Cover: growth opportunities, customer trends, churn risks, marketing recommendations,
and revenue insight. Be specific with numbers. Professional, confident, no bullet lists.
"""


def generate_weekly_report(org_id: Optional[str]) -> dict:
    bundle = generate_strategy(org_id)
    try:
        resp = _groq().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": WEEKLY_REPORT_PROMPT},
                {"role": "user", "content": json.dumps(bundle, default=str)[:6000]},
            ],
            temperature=0.5,
            max_tokens=700,
        )
        narrative = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Weekly report LLM failed: {e}")
        narrative = bundle["strategy"].get("headline", "Strategic report unavailable.")
    return {**bundle, "narrative": narrative}
