"""
CRM router — Customers.

Endpoints:
  GET  /customers          — paginated list with scores
  GET  /customers/{id}     — full profile + AI 360 summary
  POST /customers          — create single customer
  POST /customers/import   — bulk CSV/JSON import
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from config import redis_client, supabase
from deps import OrgContext, get_org
from models.customer import (
    CustomerCreate,
    CustomerDetailedRead,
    CustomerListResponse,
    CustomerRead,
    ImportResponse,
)
from services.ai_engine import generate_customer_summary

logger = logging.getLogger(__name__)

router = APIRouter()

# Regular expressions for validation
PHONE_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")
EMAIL_PATTERN = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


@router.get("/customers", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    search: str = Query(None),
    churn_risk: str = Query(None),
    sort_by: str = Query("spend"),
    sort_dir: str = Query("desc"),
    org: OrgContext = Depends(get_org),
):
    """Return paginated customers joined with their RFM scores."""
    start = (page - 1) * limit
    end = start + limit - 1

    # Churn risk filtering requires an inner join to discard customers without scores.
    # Otherwise, perform a left join to include customers without order history yet.
    if churn_risk:
        select_str = "*, score:customer_scores!inner(*)"
    else:
        select_str = "*, score:customer_scores(*)"

    try:
        query = supabase.table("customers").select(select_str, count="exact")
        query = org.scope(query)

        if search:
            search_clean = search.strip()
            query = query.or_(
                f"first_name.ilike.%{search_clean}%,"
                f"last_name.ilike.%{search_clean}%,"
                f"email.ilike.%{search_clean}%,"
                f"phone.ilike.%{search_clean}%"
            )

        if churn_risk:
            query = query.eq("score.churn_risk", churn_risk)

        # Apply sorting
        if sort_by == "spend":
            query = query.order("score(monetary)", desc=(sort_dir == "desc"))
        elif sort_by == "recency":
            query = query.order("score(recency_days)", desc=(sort_dir == "desc"))
        elif sort_by == "frequency":
            query = query.order("score(frequency)", desc=(sort_dir == "desc"))
        elif sort_by == "rfm_score":
            query = query.order("score(rfm_score)", desc=(sort_dir == "desc"))
        else:
            # Default sorting: creation date
            query = query.order("created_at", desc=(sort_dir == "desc"))

        query = query.range(start, end)
        res = query.execute()

        data = []
        for row in res.data:
            # PostgREST inner/left join yields list or None/dict
            score_val = row.get("score")
            if isinstance(score_val, list):
                row["score"] = score_val[0] if score_val else None
            elif not score_val:
                row["score"] = None
            data.append(row)

        total = res.count if res.count is not None else len(data)

        return {
            "data": data,
            "total": total,
            "page": page,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"Error listing customers: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")


@router.get("/customers/{customer_id}", response_model=CustomerDetailedRead)
async def get_customer(customer_id: UUID, org: OrgContext = Depends(get_org)):
    """Full customer profile with AI 360 summary (cached 1 h in Redis)."""
    # 1. Fetch customer info + score (scoped to the caller's org)
    cust_res = org.scope(
        supabase.table("customers")
        .select("*, score:customer_scores(*)")
        .eq("id", str(customer_id))
    ).execute()
    if not cust_res.data:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = cust_res.data[0]
    score_val = customer.get("score")
    if isinstance(score_val, list):
        customer["score"] = score_val[0] if score_val else None
    elif not score_val:
        customer["score"] = None

    # 2. Fetch order history
    orders_res = (
        supabase.table("orders")
        .select("*")
        .eq("customer_id", str(customer_id))
        .order("order_date", desc=True)
        .execute()
    )
    customer["orders"] = orders_res.data or []

    # 3. Fetch campaigns this customer was part of
    comms_res = (
        supabase.table("communications")
        .select("*, campaign:campaigns(*)")
        .eq("customer_id", str(customer_id))
        .execute()
    )
    campaigns = []
    seen_campaign_ids = set()
    for comm in (comms_res.data or []):
        camp = comm.get("campaign")
        if isinstance(camp, list):
            camp = camp[0] if camp else None
        if camp and camp["id"] not in seen_campaign_ids:
            seen_campaign_ids.add(camp["id"])
            campaigns.append(camp)
    customer["campaigns"] = campaigns

    # 4. Handle AI 360 summary caching (cached 1 hour in Redis)
    cache_key = f"customer:summary:{customer_id}"
    ai_summary = None

    try:
        ai_summary = redis_client.get(cache_key)
    except Exception as redis_err:
        logger.warning(f"Redis cache read failed: {redis_err}")

    if not ai_summary:
        try:
            # Generate new summary using AI engine
            ai_summary = generate_customer_summary(customer, customer["orders"], campaigns)
            # Try caching in Redis for 1 hour (3600 seconds)
            try:
                redis_client.setex(cache_key, 3600, ai_summary)
            except Exception as redis_err:
                logger.warning(f"Redis cache write failed: {redis_err}")
        except Exception as ai_err:
            logger.error(f"AI summary generation failed: {ai_err}")
            ai_summary = "AI summary temporarily unavailable."

    customer["ai_summary"] = ai_summary
    return customer


@router.delete("/customers")
async def delete_all_customers(org: OrgContext = Depends(get_org)):
    """
    Remove ALL customers in the organization (and, via cascade, their orders,
    scores, and communications). Destructive — the UI guards this with a
    confirmation. Admin must act within a specific org.
    """
    org_id = org.require_org()
    try:
        res = supabase.table("customers").delete().eq("org_id", org_id).execute()
        return {"deleted_all": True, "count": len(res.data or [])}
    except Exception as e:
        logger.error(f"Error deleting all customers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: UUID, org: OrgContext = Depends(get_org)):
    """Delete a single customer (org-scoped). Cascades to their orders/scores/messages."""
    try:
        found = org.scope(
            supabase.table("customers").select("id").eq("id", str(customer_id))
        ).execute()
        if not found.data:
            raise HTTPException(status_code=404, detail="Customer not found.")
        org.scope(
            supabase.table("customers").delete().eq("id", str(customer_id))
        ).execute()
        return {"deleted": True, "id": str(customer_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(body: CustomerCreate, org: OrgContext = Depends(get_org)):
    """Create a single customer and trigger RFM scoring."""
    payload = org.stamp(body.model_dump(exclude_unset=True))

    try:
        # Check uniqueness constraints proactively to return clean 400s (within org)
        if payload.get("phone"):
            dup_phone = org.scope(
                supabase.table("customers").select("id").eq("phone", payload["phone"])
            ).execute()
            if dup_phone.data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Customer with phone '{payload['phone']}' already exists.",
                )

        if payload.get("email"):
            dup_email = org.scope(
                supabase.table("customers").select("id").eq("email", payload["email"])
            ).execute()
            if dup_email.data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Customer with email '{payload['email']}' already exists.",
                )

        # Insert customer
        res = supabase.table("customers").insert(payload).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Database insert returned empty result.")

        new_cust = res.data[0]

        # Trigger RFM scoring asynchronously
        from tasks.score_customers import score_single_customer
        score_single_customer.delay(new_cust["id"])

        # Build the semantic embedding in the background (non-blocking)
        from services.customer_embedder import safe_embed_async
        safe_embed_async([new_cust["id"]])

        return new_cust

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/customers/import", response_model=ImportResponse)
async def import_customers(file: UploadFile = File(...), org: OrgContext = Depends(get_org)):
    """Bulk import customers from a CSV or JSON file (legacy; prefer /imports)."""
    org.require_org()
    # Create the import tracker record
    import_record = {
        "filename": file.filename,
        "rows_total": 0,
        "rows_imported": 0,
        "rows_failed": 0,
        "status": "processing",
        "error_log": [],
    }
    
    try:
        import_res = supabase.table("imports").insert(import_record).execute()
        if not import_res.data:
            raise HTTPException(status_code=500, detail="Failed to initialize import logs in database.")
        import_id = import_res.data[0]["id"]
    except Exception as e:
        logger.error(f"Failed to write import record: {e}")
        raise HTTPException(status_code=500, detail=f"Database log error: {e}")

    try:
        content = await file.read()
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith(".json"):
            df = pd.read_json(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Use CSV or JSON.")

        rows_total = len(df)
        valid_rows = []
        errors = []

        # Query existing customer constraints to avoid duplicates/integrity errors (within org)
        existing_res = org.scope(
            supabase.table("customers").select("id, external_id, phone, email")
        ).execute()
        existing_by_ext = {c["external_id"]: c for c in existing_res.data if c.get("external_id")}
        existing_by_phone = {c["phone"]: c for c in existing_res.data if c.get("phone")}
        existing_by_email = {c["email"]: c for c in existing_res.data if c.get("email")}

        for index, row_series in df.iterrows():
            row_num = index + 1
            row_dict = row_series.dropna().to_dict()

            # 1. Validation: First Name
            first_name = row_dict.get("first_name")
            if not first_name or not isinstance(first_name, str) or not first_name.strip():
                errors.append({"row": row_num, "reason": "first_name is required."})
                continue
            row_dict["first_name"] = str(first_name).strip()

            if "last_name" in row_dict:
                row_dict["last_name"] = str(row_dict["last_name"]).strip()

            # 2. Validation: Phone format
            phone = row_dict.get("phone")
            if phone:
                phone = str(phone).strip()
                if not PHONE_PATTERN.match(phone):
                    errors.append({"row": row_num, "reason": f"invalid phone number format: {phone}. Use E.164."})
                    continue
                row_dict["phone"] = phone

            # 3. Validation: Email format
            email = row_dict.get("email")
            if email:
                email = str(email).strip().lower()
                if not EMAIL_PATTERN.match(email):
                    errors.append({"row": row_num, "reason": f"invalid email format: {email}."})
                    continue
                row_dict["email"] = email

            # 4. Validation: Channel Preference
            pref = row_dict.get("channel_pref", "whatsapp")
            if pref not in ["whatsapp", "sms", "email", "rcs"]:
                errors.append({"row": row_num, "reason": f"invalid channel_pref: '{pref}'."})
                continue
            row_dict["channel_pref"] = pref

            # 5. Check duplicate keys against DB to prevent crash
            ext_id = row_dict.get("external_id")
            existing_ext = existing_by_ext.get(ext_id) if ext_id else None

            if phone:
                conflict_phone = existing_by_phone.get(phone)
                if conflict_phone:
                    if not existing_ext or existing_ext["id"] != conflict_phone["id"]:
                        errors.append({"row": row_num, "reason": f"phone {phone} already belongs to another customer."})
                        continue

            if email:
                conflict_email = existing_by_email.get(email)
                if conflict_email:
                    if not existing_ext or existing_ext["id"] != conflict_email["id"]:
                        errors.append({"row": row_num, "reason": f"email {email} already belongs to another customer."})
                        continue

            valid_rows.append(row_dict)

        # Upsert valid rows
        rows_imported = 0
        if valid_rows:
            # Assign external ID if none provided + stamp org_id
            for r in valid_rows:
                if not r.get("external_id"):
                    r["external_id"] = f"IMP_{uuid.uuid4().hex[:12].upper()}"
                r["org_id"] = org.require_org()

            chunk_size = 100
            inserted_ids = []
            for i in range(0, len(valid_rows), chunk_size):
                chunk = valid_rows[i : i + chunk_size]
                # Plain insert: the (org_id, external_id) unique index is partial,
                # so ON CONFLICT upsert can't target it.
                res = supabase.table("customers").insert(chunk).execute()
                inserted_ids.extend([item["id"] for item in res.data])

            rows_imported = len(valid_rows)

            # Trigger background scoring task in Celery
            if inserted_ids:
                from tasks.score_customers import batch_score_customers
                batch_score_customers.delay(inserted_ids)

        status_str = "completed" if len(errors) < rows_total else "failed"

        # Update import log entry
        supabase.table("imports").update({
            "rows_total": rows_total,
            "rows_imported": rows_imported,
            "rows_failed": len(errors),
            "status": status_str,
            "error_log": errors,
        }).eq("id", import_id).execute()

        return {
            "import_id": str(import_id),
            "rows_total": rows_total,
            "rows_imported": rows_imported,
            "rows_failed": len(errors),
            "status": status_str,
            "errors": errors,
        }

    except Exception as err:
        logger.error(f"Import process failed: {err}")
        supabase.table("imports").update({
            "status": "failed",
            "error_log": [{"row": "system", "reason": str(err)}],
        }).eq("id", import_id).execute()
        raise HTTPException(status_code=500, detail=f"Import execution error: {err}")
