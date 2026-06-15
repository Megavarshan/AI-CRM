"""
CRM router — Segments.

Endpoints:
  GET  /segments                   — list all segments
  POST /segments                   — create from filter spec
  POST /segments/nl2segment        — NL → filter spec → count + preview
  POST /segments/{id}/refresh      — re-run query, update count
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from config import supabase
from deps import OrgContext, get_org
from models.segment import NL2SegmentRequest, NL2SegmentResponse, SegmentCreate, SegmentRead
from services.segment_executor import execute_filter_spec

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/segments", response_model=list[SegmentRead])
async def list_segments(org: OrgContext = Depends(get_org)):
    """Return all saved segments, ordered by most recently created."""
    try:
        res = (
            org.scope(supabase.table("segments").select("*"))
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"Error listing segments: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")


@router.post("/segments", response_model=SegmentRead, status_code=status.HTTP_201_CREATED)
async def create_segment(body: SegmentCreate, org: OrgContext = Depends(get_org)):
    """Create a segment from a structured filter spec and compute initial count."""
    try:
        # Execute the filter spec to get the live customer count + preview (org-scoped)
        filter_dict = body.filter_spec.model_dump()
        customer_count, _ = execute_filter_spec(filter_dict, org.org_id)

        payload = org.stamp({
            "name": body.name,
            "description": body.description,
            "filter_spec": filter_dict,
            "nl_query": body.nl_query,
            "customer_count": customer_count,
        })

        res = supabase.table("segments").insert(payload).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Database insert returned empty result.")

        return res.data[0]

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating segment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/segments/nl2segment", response_model=NL2SegmentResponse)
async def nl_to_segment_endpoint(body: NL2SegmentRequest, org: OrgContext = Depends(get_org)):
    """
    Flagship AI feature.
    Translate a natural language query → filter_spec → customer count + preview.

    Flow:
      1. Send query to Groq → get structured filter_spec JSON
      2. Validate the returned filter_spec fields and operators
      3. Execute filter_spec against Supabase → count + preview names
      4. Return all three: filter_spec, count, preview, nl_query
    """
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # Step 1: Call AI engine to translate NL → filter_spec
    try:
        from services.ai_engine import nl_to_segment
        filter_spec = nl_to_segment(body.query.strip())
    except json.JSONDecodeError as jde:
        logger.error(f"AI returned invalid JSON for query '{body.query}': {jde}")
        raise HTTPException(
            status_code=422,
            detail="AI returned an invalid filter spec. Try rephrasing your query.",
        )
    except Exception as ai_err:
        logger.error(f"AI engine error for NL2Segment: {ai_err}")
        raise HTTPException(
            status_code=502,
            detail=f"AI service error: {ai_err}",
        )

    # Step 2: Validate & execute (scoped to the caller's org)
    try:
        customer_count, preview = execute_filter_spec(filter_spec, org.org_id)
    except ValueError as ve:
        logger.warning(f"Filter spec validation failed: {ve}")
        raise HTTPException(status_code=422, detail=f"Invalid filter spec from AI: {ve}")
    except Exception as exec_err:
        logger.error(f"Segment execution error: {exec_err}")
        raise HTTPException(status_code=500, detail=f"Segment execution failed: {exec_err}")

    return {
        "filter_spec": filter_spec,
        "customer_count": customer_count,
        "preview": preview,
        "nl_query": body.query.strip(),
    }


@router.post("/segments/{segment_id}/refresh")
async def refresh_segment(segment_id: UUID, org: OrgContext = Depends(get_org)):
    """Re-execute the segment query and update the cached customer count."""
    try:
        # Fetch the segment (scoped to org)
        seg_res = org.scope(
            supabase.table("segments").select("*").eq("id", str(segment_id))
        ).execute()
        if not seg_res.data:
            raise HTTPException(status_code=404, detail="Segment not found.")

        segment = seg_res.data[0]
        filter_spec = segment.get("filter_spec")

        if not filter_spec:
            raise HTTPException(status_code=400, detail="Segment has no filter_spec.")

        # Re-execute the filter spec (org-scoped)
        customer_count, preview = execute_filter_spec(filter_spec, org.org_id)

        # Update the count in the database
        supabase.table("segments").update({
            "customer_count": customer_count,
        }).eq("id", str(segment_id)).execute()

        return {
            "segment_id": str(segment_id),
            "customer_count": customer_count,
            "preview": preview,
            "refreshed": True,
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing segment {segment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
