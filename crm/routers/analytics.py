"""
CRM router — Analytics.

Endpoints:
  GET /analytics/overview   — top-level KPIs
  GET /analytics/campaigns  — per-campaign performance (last 90 days)
  GET /analytics/channels   — channel comparison metrics
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException

from config import supabase
from deps import OrgContext, get_org

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/analytics/overview")
async def analytics_overview(org: OrgContext = Depends(get_org)):
    """
    Returns top-level aggregate KPIs:
      total_customers, customers_at_risk, active_campaigns,
      revenue_influenced_30d, messages_delivered_30d, avg_open_rate_30d
    """
    try:
        now = datetime.now(timezone.utc)
        date_30d_ago = (now - timedelta(days=30)).isoformat()

        # 1. Total customers count
        total_cust_res = org.scope(
            supabase.table("customers").select("id", count="exact")
        ).limit(1).execute()
        total_customers = total_cust_res.count if total_cust_res.count is not None else 0

        # 2. Customers at risk
        at_risk_res = org.scope(
            supabase.table("customer_scores")
            .select("customer_id", count="exact")
            .in_("churn_risk", ["high", "critical"])
        ).limit(1).execute()
        customers_at_risk = at_risk_res.count if at_risk_res.count is not None else 0

        # 3. Active campaigns count
        active_camps_res = org.scope(
            supabase.table("campaigns")
            .select("id", count="exact")
            .eq("status", "running")
        ).limit(1).execute()
        active_campaigns = active_camps_res.count if active_camps_res.count is not None else 0

        # 4. Revenue influenced last 30 days
        orders_res = org.scope(
            supabase.table("orders")
            .select("amount")
            .filter("order_date", "gte", date_30d_ago)
        ).execute()
        revenue_influenced_30d = sum(float(row["amount"]) for row in (orders_res.data or []))

        # 5. Messages delivered last 30 days
        delivered_res = org.scope(
            supabase.table("communications")
            .select("id", count="exact")
            .eq("status", "delivered")
            .filter("delivered_at", "gte", date_30d_ago)
        ).limit(1).execute()
        messages_delivered_30d = delivered_res.count if delivered_res.count is not None else 0

        # 6. Avg open rate last 30 days
        camps_res = org.scope(
            supabase.table("campaigns")
            .select("total_delivered, total_opened")
            .filter("launched_at", "gte", date_30d_ago)
        ).execute()
        total_opened = sum(row.get("total_opened", 0) for row in (camps_res.data or []))
        total_delivered = sum(row.get("total_delivered", 0) for row in (camps_res.data or []))
        avg_open_rate_30d = round((total_opened / total_delivered) * 100, 1) if total_delivered > 0 else 0.0

        return {
            "total_customers": total_customers,
            "customers_at_risk": customers_at_risk,
            "active_campaigns": active_campaigns,
            "revenue_influenced_30d": revenue_influenced_30d,
            "messages_delivered_30d": messages_delivered_30d,
            "avg_open_rate_30d": avg_open_rate_30d,
        }

    except Exception as e:
        logger.error(f"Error compiling analytics overview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch overview metrics: {e}")


@router.get("/analytics/campaigns")
async def analytics_campaigns(org: OrgContext = Depends(get_org)):
    """Per-campaign performance for last 90 days, sorted by open_rate desc."""
    try:
        now = datetime.now(timezone.utc)
        date_90d_ago = (now - timedelta(days=90)).isoformat()

        res = org.scope(
            supabase.table("campaigns")
            .select("id, name, status, channel, total_sent, total_delivered, total_opened, total_clicked, created_at")
            .filter("created_at", "gte", date_90d_ago)
        ).execute()
        campaigns = res.data or []

        result = []
        for c in campaigns:
            sent = c.get("total_sent", 0)
            delivered = c.get("total_delivered", 0)
            opened = c.get("total_opened", 0)
            clicked = c.get("total_clicked", 0)
            
            delivery_rate = round((delivered / sent) * 100, 1) if sent > 0 else 0.0
            open_rate = round((opened / delivered) * 100, 1) if delivered > 0 else 0.0
            click_rate = round((clicked / opened) * 100, 1) if opened > 0 else 0.0
            
            result.append({
                "id": c["id"],
                "name": c["name"],
                "status": c["status"],
                "channel": c["channel"],
                "total_sent": sent,
                "total_delivered": delivered,
                "total_opened": opened,
                "total_clicked": clicked,
                "delivery_rate": delivery_rate,
                "open_rate": open_rate,
                "click_rate": click_rate,
                "created_at": c["created_at"],
            })

        # Sort by open_rate desc
        result.sort(key=lambda x: x["open_rate"], reverse=True)
        return result

    except Exception as e:
        logger.error(f"Error fetching campaign performance analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/raw-data")
async def analytics_raw_data(org: OrgContext = Depends(get_org)):
    """
    Aggregations over the raw customers + orders tables for the Data
    visualization page: monthly trends, category/city/channel splits,
    spend distribution, and headline totals.
    """
    try:
        # Paginated full fetch (PostgREST caps responses at 1000 rows)
        def fetch_all(table: str, fields: str) -> list[dict]:
            out: list[dict] = []
            offset, chunk = 0, 1000
            while True:
                res = org.scope(
                    supabase.table(table).select(fields)
                ).range(offset, offset + chunk - 1).execute()
                if not res.data:
                    break
                out.extend(res.data)
                if len(res.data) < chunk:
                    break
                offset += chunk
            return out

        orders = fetch_all("orders", "order_date, amount, category, status")
        customers = fetch_all("customers", "city, channel_pref, created_at")
        scores = fetch_all("customer_scores", "monetary, churn_risk")

        # ── Monthly orders + revenue (completed only) ────────────────────
        monthly: dict[str, dict] = {}
        category: dict[str, dict] = {}
        status_counts: dict[str, int] = {}
        total_revenue = 0.0
        completed_orders = 0

        for o in orders:
            st = o.get("status") or "completed"
            status_counts[st] = status_counts.get(st, 0) + 1
            month = (o.get("order_date") or "")[:7]  # YYYY-MM
            amt = float(o.get("amount") or 0)
            if st == "completed":
                completed_orders += 1
                total_revenue += amt
                if month:
                    m = monthly.setdefault(month, {"month": month, "orders": 0, "revenue": 0.0})
                    m["orders"] += 1
                    m["revenue"] += amt
                cat = (o.get("category") or "uncategorised").lower()
                c = category.setdefault(cat, {"category": cat, "orders": 0, "revenue": 0.0})
                c["orders"] += 1
                c["revenue"] += amt

        monthly_list = sorted(monthly.values(), key=lambda x: x["month"])
        for m in monthly_list:
            m["revenue"] = round(m["revenue"], 2)
        category_list = sorted(category.values(), key=lambda x: x["revenue"], reverse=True)
        for c in category_list:
            c["revenue"] = round(c["revenue"], 2)

        # ── Customers: city + channel splits ─────────────────────────────
        city_counts: dict[str, int] = {}
        channel_counts: dict[str, int] = {}
        for cust in customers:
            city = cust.get("city") or "Unknown"
            city_counts[city] = city_counts.get(city, 0) + 1
            ch = cust.get("channel_pref") or "whatsapp"
            channel_counts[ch] = channel_counts.get(ch, 0) + 1

        cities = sorted(
            ({"city": k, "customers": v} for k, v in city_counts.items()),
            key=lambda x: x["customers"], reverse=True,
        )[:10]
        channels = [{"channel": k, "customers": v} for k, v in sorted(channel_counts.items())]

        # ── Spend distribution buckets ────────────────────────────────────
        buckets = [
            ("0-2k", 0, 2000), ("2k-5k", 2000, 5000), ("5k-10k", 5000, 10000),
            ("10k-20k", 10000, 20000), ("20k-40k", 20000, 40000), ("40k+", 40000, float("inf")),
        ]
        spend_dist = [{"bucket": label, "customers": 0} for label, _, _ in buckets]
        churn_counts: dict[str, int] = {}
        for s in scores:
            mon = float(s.get("monetary") or 0)
            for i, (_, lo, hi) in enumerate(buckets):
                if lo <= mon < hi:
                    spend_dist[i]["customers"] += 1
                    break
            cr = s.get("churn_risk") or "unknown"
            churn_counts[cr] = churn_counts.get(cr, 0) + 1

        churn = [
            {"risk": r, "customers": churn_counts.get(r, 0)}
            for r in ("low", "medium", "high", "critical")
        ]

        return {
            "summary": {
                "total_customers": len(customers),
                "total_orders": len(orders),
                "completed_orders": completed_orders,
                "total_revenue": round(total_revenue, 2),
                "avg_order_value": round(total_revenue / completed_orders, 2) if completed_orders else 0,
            },
            "monthly": monthly_list,
            "categories": category_list,
            "cities": cities,
            "channels": channels,
            "spend_distribution": spend_dist,
            "order_status": [{"status": k, "orders": v} for k, v in sorted(status_counts.items())],
            "churn": churn,
        }

    except Exception as e:
        logger.error(f"Error compiling raw data analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/channels")
async def analytics_channels(org: OrgContext = Depends(get_org)):
    """Channel-by-channel open/click rate comparison aggregated from all campaigns."""
    try:
        res = org.scope(
            supabase.table("campaigns")
            .select("channel, total_sent, total_delivered, total_opened, total_clicked")
        ).execute()
        data = res.data or []

        breakdown = {}
        for row in data:
            ch = row["channel"]
            if ch not in breakdown:
                breakdown[ch] = {"sent": 0, "delivered": 0, "opened": 0, "clicked": 0}
            breakdown[ch]["sent"] += row.get("total_sent", 0)
            breakdown[ch]["delivered"] += row.get("total_delivered", 0)
            breakdown[ch]["opened"] += row.get("total_opened", 0)
            breakdown[ch]["clicked"] += row.get("total_clicked", 0)

        result = []
        for ch, stats in breakdown.items():
            sent = stats["sent"]
            delivered = stats["delivered"]
            opened = stats["opened"]
            clicked = stats["clicked"]
            
            delivery_rate = round((delivered / sent) * 100, 1) if sent > 0 else 0.0
            open_rate = round((opened / delivered) * 100, 1) if delivered > 0 else 0.0
            click_rate = round((clicked / opened) * 100, 1) if opened > 0 else 0.0
            
            result.append({
                "channel": ch,
                "total_sent": sent,
                "delivery_rate": delivery_rate,
                "open_rate": open_rate,
                "click_rate": click_rate,
            })

        return result

    except Exception as e:
        logger.error(f"Error compiling channel comparison analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
