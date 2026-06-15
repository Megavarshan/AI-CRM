"""
Semantic search — RAG retrieval over the customer vector store.

Embeds a natural-language query, runs an org-scoped ANN search via the
match_customers / similar_customers pgvector RPCs, and enriches the hits with
their RFM scores + a human-readable "why it matched" profile snippet.
"""

from __future__ import annotations

import logging
from typing import Optional

from config import supabase
from services.embeddings import customer_document, embed_query, to_pgvector

logger = logging.getLogger(__name__)


def _enrich(hits: list[dict], org_id: Optional[str]) -> list[dict]:
    """Attach RFM score + profile snippet to RPC hits, preserving rank order."""
    if not hits:
        return []
    ids = [h["id"] for h in hits]
    q = supabase.table("customers").select(
        "id, first_name, last_name, city, channel_pref, score:customer_scores(*)"
    ).in_("id", ids)
    if org_id:
        q = q.eq("org_id", org_id)
    rows = {r["id"]: r for r in (q.execute().data or [])}

    out = []
    for h in hits:
        r = rows.get(h["id"])
        if not r:
            continue  # filtered out by org scope
        score = r.get("score")
        if isinstance(score, list):
            score = score[0] if score else None
        out.append({
            "id": r["id"],
            "first_name": r["first_name"],
            "last_name": r.get("last_name"),
            "city": r.get("city"),
            "channel_pref": r.get("channel_pref"),
            "similarity": round(float(h.get("similarity", 0)), 4),
            "score": score,
            "why": customer_document(r, score or {}),
        })
    return out


def semantic_search(query: str, org_id: Optional[str], limit: int = 12) -> dict:
    """NL query → vector → ranked customers (org-scoped)."""
    vec = embed_query(query)
    # Over-fetch so org filtering in enrich still yields enough rows for admin/orgs.
    rpc = supabase.rpc("match_customers", {
        "query_embedding": to_pgvector(vec),
        "match_org": org_id,
        "match_count": limit if org_id else limit * 2,
    }).execute()
    hits = rpc.data or []
    results = _enrich(hits, org_id)[:limit]
    return {"query": query, "count": len(results), "results": results}


def find_similar(customer_id: str, org_id: Optional[str], limit: int = 8) -> dict:
    """Lookalike discovery: nearest neighbours to an existing customer."""
    rpc = supabase.rpc("similar_customers", {
        "source_id": customer_id,
        "match_org": org_id,
        "match_count": limit if org_id else limit * 2,
    }).execute()
    hits = rpc.data or []
    return {"source_id": customer_id, "results": _enrich(hits, org_id)[:limit]}


def retrieve_context(query: str, org_id: Optional[str], k: int = 6) -> list[dict]:
    """Compact retrieval used to GROUND the Copilot / Strategist (RAG)."""
    res = semantic_search(query, org_id, limit=k)
    return [
        {
            "name": f"{r['first_name']} {r.get('last_name') or ''}".strip(),
            "similarity": r["similarity"],
            "profile": r["why"],
        }
        for r in res["results"]
    ]
