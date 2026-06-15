"""
CRM router — Semantic (RAG) customer intelligence.

  POST /customers/semantic-search   — NL query → vector → ranked customers
  GET  /customers/{id}/similar       — lookalike discovery
  POST /segments/from-semantic       — save a semantic search as a segment

All org-scoped via the X-Org-Id header.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import supabase
from deps import OrgContext, get_org
from services import semantic as semantic_svc

logger = logging.getLogger(__name__)

router = APIRouter()


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    limit: int = Field(12, ge=1, le=50)


@router.post("/customers/semantic-search")
async def semantic_search(body: SemanticSearchRequest, org: OrgContext = Depends(get_org)):
    """Retrieve customers by semantic meaning of a natural-language query."""
    try:
        return semantic_svc.semantic_search(body.query.strip(), org.org_id, body.limit)
    except Exception as e:
        msg = str(e)
        if "match_customers" in msg or "does not exist" in msg or "schema cache" in msg:
            raise HTTPException(
                status_code=503,
                detail="Vector search not set up. Run crm/db/migrations/004_pgvector_rag.sql and "
                       "python db/backfill_embeddings.py.",
            )
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=msg)


@router.get("/customers/{customer_id}/similar")
async def similar_customers(customer_id: UUID, org: OrgContext = Depends(get_org)):
    """Find lookalike customers (nearest neighbours in embedding space)."""
    try:
        return semantic_svc.find_similar(str(customer_id), org.org_id)
    except Exception as e:
        logger.error(f"Lookalike search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SemanticSegmentRequest(BaseModel):
    name: str
    query: str
    customer_ids: list[str]


@router.post("/segments/from-semantic")
async def segment_from_semantic(body: SemanticSegmentRequest, org: OrgContext = Depends(get_org)):
    """
    Persist a semantic search result as a static segment (an explicit id list),
    so it can drive a campaign like any other segment.
    """
    spec = {"operator": "AND", "conditions": [], "semantic_query": body.query, "static_ids": body.customer_ids}
    payload = org.stamp({
        "name": body.name,
        "description": f"Semantic (AI) segment from: {body.query}",
        "filter_spec": spec,
        "nl_query": body.query,
        "customer_count": len(body.customer_ids),
    })
    res = supabase.table("segments").insert(payload).execute()
    return res.data[0] if res.data else {"error": "insert failed"}
