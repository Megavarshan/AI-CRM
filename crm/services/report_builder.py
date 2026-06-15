"""
PDF Report Builder — executive business reports with charts, KPIs, an AI
business-analysis section, and strategic recommendations from the Strategist.

Pure reportlab (platypus + graphics), org-scoped, returns PDF bytes.
Report types: customer | campaign | engagement | executive
"""

from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.lineplots import LinePlot

from config import settings, supabase
from services import strategist as strategist_svc

logger = logging.getLogger(__name__)

PURPLE = colors.HexColor("#7c3aed")
INDIGO = colors.HexColor("#6366f1")
TEAL = colors.HexColor("#14b8a6")
SLATE = colors.HexColor("#334155")
LIGHT = colors.HexColor("#e2e8f0")
PIE_COLORS = [PURPLE, INDIGO, colors.HexColor("#e879f9"),
              colors.HexColor("#38bdf8"), TEAL, colors.HexColor("#fbbf24")]


def _org(query, org_id: Optional[str]):
    return query.eq("org_id", org_id) if org_id else query


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("OrbitTitle", parent=ss["Title"], textColor=PURPLE, fontSize=22, spaceAfter=2))
    ss.add(ParagraphStyle("OrbitSub", parent=ss["Normal"], textColor=SLATE, fontSize=10, spaceAfter=12))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], textColor=INDIGO, fontSize=13, spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=9.5, leading=14, alignment=TA_LEFT, spaceAfter=6))
    ss.add(ParagraphStyle("AIBody", parent=ss["Normal"], fontSize=9.5, leading=14, textColor=colors.HexColor("#1e293b")))
    ss.add(ParagraphStyle("Rec", parent=ss["Normal"], fontSize=9.5, leading=14, leftIndent=10, spaceAfter=3))
    return ss


# ── Data gathering (org-scoped) ──────────────────────────────────────────────

def _fetch_all(table: str, fields: str, org_id: Optional[str]) -> list[dict]:
    out: list[dict] = []
    offset, chunk = 0, 1000
    while True:
        res = _org(supabase.table(table).select(fields), org_id).range(offset, offset + chunk - 1).execute()
        if not res.data:
            break
        out.extend(res.data)
        if len(res.data) < chunk:
            break
        offset += chunk
    return out


def gather_report_data(org_id: Optional[str]) -> dict:
    orders = _fetch_all("orders", "order_date, amount, category, status", org_id)
    customers = _fetch_all("customers", "city, channel_pref", org_id)
    scores = _fetch_all("customer_scores", "monetary, churn_risk", org_id)
    campaigns = _org(
        supabase.table("campaigns").select(
            "name, channel, status, total_sent, total_delivered, total_opened, total_clicked, total_failed"
        ), org_id,
    ).execute().data or []

    monthly: dict[str, dict] = {}
    category: dict[str, float] = {}
    revenue = 0.0
    completed = 0
    for o in orders:
        if (o.get("status") or "completed") != "completed":
            continue
        completed += 1
        amt = float(o.get("amount") or 0)
        revenue += amt
        m = (o.get("order_date") or "")[:7]
        if m:
            monthly.setdefault(m, {"month": m, "revenue": 0.0})["revenue"] += amt
        cat = (o.get("category") or "other").lower()
        category[cat] = category.get(cat, 0) + amt

    churn = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for s in scores:
        cr = s.get("churn_risk")
        if cr in churn:
            churn[cr] += 1

    cities: dict[str, int] = {}
    channels: dict[str, int] = {}
    for c in customers:
        cities[c.get("city") or "Unknown"] = cities.get(c.get("city") or "Unknown", 0) + 1
        channels[c.get("channel_pref") or "whatsapp"] = channels.get(c.get("channel_pref") or "whatsapp", 0) + 1

    # Channel engagement from campaigns
    ch_perf: dict[str, dict] = {}
    tot = {"sent": 0, "delivered": 0, "opened": 0, "clicked": 0, "failed": 0}
    for c in campaigns:
        ch = c.get("channel") or "whatsapp"
        d = ch_perf.setdefault(ch, {"delivered": 0, "opened": 0, "clicked": 0})
        d["delivered"] += c.get("total_delivered", 0)
        d["opened"] += c.get("total_opened", 0)
        d["clicked"] += c.get("total_clicked", 0)
        for k in tot:
            tot[k] += c.get(f"total_{k}", 0)

    return {
        "customers": customers, "scores": scores, "campaigns": campaigns,
        "monthly": sorted(monthly.values(), key=lambda x: x["month"]),
        "category": sorted(category.items(), key=lambda kv: kv[1], reverse=True),
        "revenue": round(revenue, 2), "completed_orders": completed,
        "total_orders": len(orders), "total_customers": len(customers),
        "churn": churn, "cities": sorted(cities.items(), key=lambda kv: kv[1], reverse=True)[:8],
        "channels": channels, "channel_perf": ch_perf, "campaign_totals": tot,
        "avg_order_value": round(revenue / completed, 2) if completed else 0,
    }


# ── Charts ───────────────────────────────────────────────────────────────────

def _bar_chart(data: list[tuple[str, float]], width=440, height=170) -> Drawing:
    d = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 30, 25, width - 60, height - 50
    chart.data = [[round(v, 0) for _, v in data]] if data else [[0]]
    chart.categoryAxis.categoryNames = [k[:10] for k, _ in data] or [""]
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = PURPLE
    chart.barWidth = 8
    d.add(chart)
    return d


def _pie_chart(data: list[tuple[str, float]], width=240, height=160) -> Drawing:
    d = Drawing(width, height)
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 60, 20, 120, 120
    vals = [v for _, v in data if v > 0]
    labels = [f"{k} ({int(v)})" for k, v in data if v > 0]
    pie.data = vals or [1]
    pie.labels = labels or ["n/a"]
    pie.slices.strokeWidth = 0.5
    pie.slices.fontSize = 7
    for i in range(len(pie.data)):
        pie.slices[i].fillColor = PIE_COLORS[i % len(PIE_COLORS)]
    d.add(pie)
    return d


def _line_chart(series: list[tuple[str, float]], width=440, height=170) -> Drawing:
    d = Drawing(width, height)
    if len(series) < 2:
        return d
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 35, 25, width - 70, height - 50
    pts = [(i, v) for i, (_, v) in enumerate(series)]
    lp.data = [pts]
    lp.lines[0].strokeColor = PURPLE
    lp.lines[0].strokeWidth = 2
    lp.xValueAxis.valueMin = 0
    lp.xValueAxis.valueMax = len(series) - 1
    lp.yValueAxis.valueMin = 0
    d.add(lp)
    return d


# ── AI business analysis ──────────────────────────────────────────────────────

def _ai_analysis(report_type: str, data: dict) -> str:
    from services.ai_engine import _get_groq_client
    summary = {
        "report_type": report_type,
        "total_customers": data["total_customers"],
        "revenue": data["revenue"],
        "avg_order_value": data["avg_order_value"],
        "churn": data["churn"],
        "top_categories": data["category"][:5],
        "channel_perf": data["channel_perf"],
        "campaign_totals": data["campaign_totals"],
    }
    prompt = (
        f"You are a marketing analyst. Write a 4-5 sentence business analysis for a {report_type} "
        f"report based on this data. Be specific with numbers, note one trend and one risk, and end "
        f"with a clear takeaway. Paragraph form only.\n\n{json.dumps(summary, default=str)}"
    )
    try:
        resp = _get_groq_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4, max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"AI analysis failed: {e}")
        return "AI analysis is temporarily unavailable for this report."


# ── PDF assembly ──────────────────────────────────────────────────────────────

def _kpi_table(pairs: list[tuple[str, str]]) -> Table:
    cells = [[Paragraph(f"<b>{v}</b>", getSampleStyleSheet()["Title"]) for _, v in pairs],
             [Paragraph(k, getSampleStyleSheet()["Normal"]) for k, _ in pairs]]
    t = Table(cells, colWidths=[(17 * cm) / len(pairs)] * len(pairs))
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 0), (-1, 0), PURPLE),
        ("FONTSIZE", (0, 0), (-1, 0), 16),
        ("FONTSIZE", (0, 1), (-1, 1), 8),
        ("TEXTCOLOR", (0, 1), (-1, 1), SLATE),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, LIGHT),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LIGHT),
    ]))
    return t


REPORT_TITLES = {
    "customer": "Customer Analytics Report",
    "campaign": "Campaign Performance Report",
    "engagement": "Engagement Intelligence Report",
    "executive": "Executive Business Report",
}


def build_report(report_type: str, org_id: Optional[str]) -> bytes:
    report_type = report_type if report_type in REPORT_TITLES else "executive"
    ss = _styles()
    data = gather_report_data(org_id)

    # Org branding
    org_name = "Orbit Platform (All Organizations)"
    if org_id:
        org_res = supabase.table("organizations").select("company_name").eq("id", org_id).execute()
        if org_res.data:
            org_name = org_res.data[0]["company_name"]

    story: list = []
    story.append(Paragraph("◆ ORBIT", ss["OrbitTitle"]))
    story.append(Paragraph(f"{REPORT_TITLES[report_type]} — {org_name}", ss["OrbitSub"]))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}", ss["Body"]))
    story.append(Spacer(1, 6))

    # KPIs
    tot = data["campaign_totals"]
    open_rate = round((tot["opened"] / tot["delivered"]) * 100, 1) if tot["delivered"] else 0
    story.append(_kpi_table([
        ("Customers", f"{data['total_customers']:,}"),
        ("Revenue", f"Rs {int(data['revenue']):,}"),
        ("Avg Order", f"Rs {int(data['avg_order_value']):,}"),
        ("Msgs Sent", f"{tot['sent']:,}"),
        ("Open Rate", f"{open_rate}%"),
    ]))
    story.append(Spacer(1, 8))

    # Sections by type
    if report_type in ("customer", "executive"):
        story.append(Paragraph("Revenue Trend", ss["H2"]))
        story.append(_line_chart([(m["month"], m["revenue"]) for m in data["monthly"]]))
        story.append(Paragraph("Churn Risk Distribution", ss["H2"]))
        story.append(_pie_chart(list(data["churn"].items())))
        story.append(Paragraph("Top Cities", ss["H2"]))
        story.append(_bar_chart([(c, n) for c, n in data["cities"]]))

    if report_type in ("campaign", "executive"):
        story.append(Paragraph("Campaign Funnel", ss["H2"]))
        story.append(_bar_chart([
            ("Sent", tot["sent"]), ("Delivered", tot["delivered"]),
            ("Opened", tot["opened"]), ("Clicked", tot["clicked"]),
        ]))

    if report_type in ("engagement", "executive"):
        story.append(Paragraph("Channel Open Rates", ss["H2"]))
        ch_rows = []
        for ch, d in data["channel_perf"].items():
            orr = round((d["opened"] / d["delivered"]) * 100, 1) if d["delivered"] else 0
            ch_rows.append((ch, orr))
        story.append(_bar_chart(ch_rows or [("n/a", 0)]))
        story.append(Paragraph("Channel Preference (audience)", ss["H2"]))
        story.append(_pie_chart(list(data["channels"].items())))

    if report_type in ("customer", "executive"):
        story.append(Paragraph("Revenue by Category", ss["H2"]))
        story.append(_bar_chart([(k, v) for k, v in data["category"][:6]]))

    # AI business analysis
    story.append(Paragraph("AI Business Analysis", ss["H2"]))
    story.append(Paragraph(_ai_analysis(report_type, data), ss["AIBody"]))

    # Strategic recommendations (from the Strategist agent)
    try:
        strat = strategist_svc.generate_strategy(org_id)["strategy"]
        recs = strat.get("recommendations", [])
        if recs:
            story.append(Paragraph("Strategic Recommendations", ss["H2"]))
            for i, r in enumerate(recs[:6], 1):
                story.append(Paragraph(f"{i}. {r}", ss["Rec"]))
    except Exception as e:
        logger.warning(f"Strategist recs for report failed: {e}")

    # Build with branded footer
    buf = io.BytesIO()

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(SLATE)
        canvas.drawString(2 * cm, 1 * cm, f"Orbit CRM · {org_name}")
        canvas.drawRightString(19 * cm, 1 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(LIGHT)
        canvas.line(2 * cm, 1.3 * cm, 19 * cm, 1.3 * cm)
        canvas.restoreState()

    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                          topMargin=1.5 * cm, bottomMargin=1.8 * cm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="orbit", frames=[frame], onPage=_footer)])
    doc.build(story)
    return buf.getvalue()
