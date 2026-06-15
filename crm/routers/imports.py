"""
CRM router — AI-assisted data imports.

Endpoints:
  POST /imports/analyze — upload a file; the AI agent detects whether it is
                          customer or order data, maps arbitrary headers to the
                          canonical schema, and proposes value mappings.
  POST /imports/run     — upload the same file + the (possibly user-adjusted)
                          mapping; ingests rows with full normalisation.

Flow in the UI: analyze → show mapping for review → run.
"""

from __future__ import annotations

import io
import json
import logging
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from config import supabase
from deps import OrgContext, get_org
from services.ai_engine import map_import_headers
from services.import_mapper import apply_mapping, build_analysis_payload

logger = logging.getLogger(__name__)

router = APIRouter()


def _read_dataframe(filename: str, content: bytes) -> pd.DataFrame:
    if filename.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    if filename.endswith(".json"):
        return pd.read_json(io.BytesIO(content))
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    raise HTTPException(status_code=400, detail="Unsupported file format. Use CSV, JSON, or Excel.")


@router.post("/imports/analyze")
async def analyze_import(file: UploadFile = File(...)):
    """Run the AI mapping agent over an uploaded file and return its proposal."""
    content = await file.read()
    df = _read_dataframe(file.filename or "upload.csv", content)
    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file has no rows.")

    headers, sample_rows, distinct_values = build_analysis_payload(df)

    try:
        analysis = map_import_headers(headers, sample_rows, distinct_values)
    except Exception as e:
        logger.error(f"AI header mapping failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI mapping agent failed: {e}")

    mapping = analysis.get("mapping", {}) or {}
    return {
        "filename": file.filename,
        "rows_total": int(len(df)),
        "entity_type": analysis.get("entity_type", "customers"),
        "confidence": analysis.get("confidence"),
        "mapping": mapping,
        "unmapped_headers": [h for h in headers if h not in mapping],
        "customer_ref_type": analysis.get("customer_ref_type"),
        "value_mappings": analysis.get("value_mappings", {}),
        "default_country_code": analysis.get("default_country_code", "+91"),
        "notes": analysis.get("notes", ""),
        "sample_rows": sample_rows[:5],
    }


@router.post("/imports/run")
async def run_import(
    file: UploadFile = File(...),
    analysis: str = Form(...),
    org: OrgContext = Depends(get_org),
):
    """Ingest a file using the supplied mapping analysis (from /imports/analyze)."""
    org_id = org.require_org()
    try:
        analysis_dict = json.loads(analysis)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid analysis JSON.")

    content = await file.read()
    df = _read_dataframe(file.filename or "upload.csv", content)
    canonical = apply_mapping(df, analysis_dict)
    entity = analysis_dict.get("entity_type", "customers")

    # Track in the imports table
    import_res = supabase.table("imports").insert({
        "filename": file.filename,
        "rows_total": int(len(df)),
        "rows_imported": 0,
        "rows_failed": 0,
        "status": "processing",
        "error_log": [],
    }).execute()
    import_id = import_res.data[0]["id"] if import_res.data else None

    try:
        if entity == "customers":
            result = _ingest_customers(canonical, org_id)
        else:
            result = _ingest_orders(canonical, analysis_dict.get("customer_ref_type") or "external_id", org_id)
    except Exception as e:
        logger.error(f"Import ingestion failed: {e}")
        if import_id:
            supabase.table("imports").update({
                "status": "failed", "error_log": [{"row": "all", "reason": str(e)[:300]}],
            }).eq("id", import_id).execute()
        # Clean error WITH CORS headers (so the UI shows it, not "failed to fetch")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)[:300]}")

    if import_id:
        supabase.table("imports").update({
            "rows_imported": result["rows_imported"],
            "rows_failed": result["rows_failed"],
            "status": "completed" if result["rows_imported"] > 0 else "failed",
            "error_log": result["errors"][:50],
        }).eq("id", import_id).execute()

    return {
        "import_id": import_id,
        "entity_type": entity,
        "rows_total": int(len(df)),
        **result,
    }


def _ingest_customers(df: pd.DataFrame, org_id: str) -> dict:
    """Validate + upsert canonical customer rows; trigger RFM scoring."""
    errors: list[dict] = []
    valid_rows: list[dict] = []

    # Existing constraints for dedup (within this org)
    existing = supabase.table("customers").select("id, external_id, phone, email").eq("org_id", org_id).execute()
    by_ext = {c["external_id"]: c for c in existing.data if c.get("external_id")}
    by_phone = {c["phone"]: c for c in existing.data if c.get("phone")}
    by_email = {c["email"]: c for c in existing.data if c.get("email")}
    seen_phones: set = set()
    seen_emails: set = set()

    for idx, row in df.iterrows():
        row_num = int(idx) + 1
        r = {k: (None if (isinstance(v, float) and pd.isna(v)) or v == "" else v) for k, v in row.to_dict().items()}

        if not r.get("first_name"):
            errors.append({"row": row_num, "reason": "missing first name"})
            continue

        phone, email, ext = r.get("phone"), r.get("email"), r.get("external_id")

        # In-file duplicate guards
        if phone and phone in seen_phones:
            errors.append({"row": row_num, "reason": f"duplicate phone in file: {phone}"})
            continue
        if email and email in seen_emails:
            errors.append({"row": row_num, "reason": f"duplicate email in file: {email}"})
            continue

        # DB conflict guards (allow if it's the same external_id being updated)
        existing_ext = by_ext.get(ext) if ext else None
        if phone and phone in by_phone and (not existing_ext or existing_ext["id"] != by_phone[phone]["id"]):
            errors.append({"row": row_num, "reason": f"phone {phone} belongs to another customer"})
            continue
        if email and email in by_email and (not existing_ext or existing_ext["id"] != by_email[email]["id"]):
            errors.append({"row": row_num, "reason": f"email {email} belongs to another customer"})
            continue

        if phone:
            seen_phones.add(phone)
        if email:
            seen_emails.add(email)
        if not ext:
            r["external_id"] = f"IMP_{uuid.uuid4().hex[:12].upper()}"
        r.setdefault("channel_pref", "whatsapp")
        r["org_id"] = org_id
        # Re-import of an existing external_id -> update that customer in place.
        if existing_ext:
            r["__update_id"] = existing_ext["id"]
        valid_rows.append(r)

    # Split into inserts vs updates. We avoid upsert(on_conflict=...) because the
    # (org_id, external_id) unique index is PARTIAL (WHERE external_id IS NOT NULL),
    # which Postgres ON CONFLICT cannot target.
    inserted_ids: list[str] = []
    to_insert = [r for r in valid_rows if "__update_id" not in r]
    to_update = [r for r in valid_rows if "__update_id" in r]

    chunk = 100
    for i in range(0, len(to_insert), chunk):
        res = supabase.table("customers").insert(to_insert[i : i + chunk]).execute()
        inserted_ids.extend(item["id"] for item in (res.data or []))

    for r in to_update:
        uid = r.pop("__update_id")
        supabase.table("customers").update(r).eq("id", uid).execute()
        inserted_ids.append(uid)

    if inserted_ids:
        try:
            from tasks.score_customers import batch_score_customers
            batch_score_customers.delay(inserted_ids)
        except Exception as e:
            # Broker unavailable — data is already imported; scoring catches up
            # on the next nightly batch. Don't fail the import.
            logger.warning(f"Could not enqueue RFM scoring (broker down?): {e}")
        # Semantic embeddings in the background (non-blocking)
        from services.customer_embedder import safe_embed_async
        safe_embed_async(inserted_ids)

    return {"rows_imported": len(valid_rows), "rows_failed": len(errors), "errors": errors}


def _ingest_orders(df: pd.DataFrame, ref_type: str, org_id: str) -> dict:
    """Resolve customer references, insert canonical order rows, re-score affected customers."""
    errors: list[dict] = []

    # Build the customer lookup for the chosen reference type (within org)
    lookup_field = {"external_id": "external_id", "email": "email", "phone": "phone"}[ref_type]
    cust = supabase.table("customers").select(f"id, {lookup_field}").eq("org_id", org_id).execute()
    lookup = {str(c[lookup_field]).strip().lower(): c["id"] for c in cust.data if c.get(lookup_field)}

    rows: list[dict] = []
    touched_customers: set = set()
    for idx, row in df.iterrows():
        row_num = int(idx) + 1
        r = row.to_dict()
        ref = r.get("customer_ref")
        if not ref:
            errors.append({"row": row_num, "reason": "missing customer reference"})
            continue
        customer_id = lookup.get(str(ref).strip().lower())
        if not customer_id:
            errors.append({"row": row_num, "reason": f"no customer found for {ref_type}={ref}"})
            continue
        if not r.get("order_date"):
            errors.append({"row": row_num, "reason": "unparseable order date"})
            continue
        amount = r.get("amount")
        if amount is None or (isinstance(amount, float) and pd.isna(amount)):
            errors.append({"row": row_num, "reason": "unparseable amount"})
            continue

        rows.append({
            "customer_id": customer_id,
            "org_id": org_id,
            "order_date": r["order_date"],
            "amount": float(amount),
            "category": (str(r["category"]).strip().lower() if r.get("category") and pd.notna(r.get("category")) else None),
            "product_name": (str(r["product_name"]).strip() if r.get("product_name") and pd.notna(r.get("product_name")) else None),
            "status": r.get("status", "completed"),
        })
        touched_customers.add(customer_id)

    chunk = 200
    for i in range(0, len(rows), chunk):
        supabase.table("orders").insert(rows[i : i + chunk]).execute()

    if touched_customers:
        try:
            from tasks.score_customers import batch_score_customers
            batch_score_customers.delay(list(touched_customers))
        except Exception as e:
            logger.warning(f"Could not enqueue RFM scoring (broker down?): {e}")

    return {"rows_imported": len(rows), "rows_failed": len(errors), "errors": errors}
