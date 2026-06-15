"""
Import Mapper — applies an AI-proposed header mapping to an uploaded dataframe
and normalises values into the canonical schema.

The LLM (ai_engine.map_import_headers) decides *what* maps to *what*;
everything in this module is deterministic so the actual ingestion is
reproducible and never depends on an LLM call per row.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)

CUSTOMER_FIELDS = {"external_id", "first_name", "last_name", "phone", "email", "city", "channel_pref"}
ORDER_FIELDS = {"customer_ref", "order_date", "amount", "category", "product_name", "status"}

CHANNEL_SYNONYMS = {
    "whatsapp": "whatsapp", "wa": "whatsapp", "whats app": "whatsapp", "wap": "whatsapp",
    "sms": "sms", "text": "sms", "txt": "sms", "message": "sms",
    "email": "email", "mail": "email", "e-mail": "email", "gmail": "email",
    "rcs": "rcs",
}

STATUS_SYNONYMS = {
    "completed": "completed", "complete": "completed", "success": "completed",
    "delivered": "completed", "paid": "completed", "fulfilled": "completed", "done": "completed",
    "returned": "returned", "return": "returned", "refunded": "returned", "refund": "returned",
    "cancelled": "cancelled", "canceled": "cancelled", "cancel": "cancelled", "void": "cancelled",
}


def build_analysis_payload(df: pd.DataFrame) -> tuple[list[str], list[dict], dict[str, list]]:
    """Extract headers, sample rows, and distinct values of low-cardinality columns."""
    headers = [str(c) for c in df.columns]
    sample_rows = df.head(8).fillna("").astype(str).to_dict(orient="records")

    distinct_values: dict[str, list] = {}
    for col in df.columns:
        uniques = df[col].dropna().astype(str).str.strip().unique()
        if 0 < len(uniques) <= 12:
            distinct_values[str(col)] = sorted(uniques.tolist())
    return headers, sample_rows, distinct_values


# ── Normalizers ──────────────────────────────────────────────────────────────

def normalize_phone(value, default_cc: str = "+91") -> str | None:
    """Coerce any phone format to E.164. Returns None if hopeless."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = re.sub(r"[^\d+]", "", str(value).strip())
    if not s:
        return None
    if s.startswith("+"):
        digits = s[1:]
        return f"+{digits}" if 7 <= len(digits) <= 15 else None
    digits = s.lstrip("0")
    cc_digits = default_cc.lstrip("+")
    # Already includes the country code without '+' (e.g. 919876543210)
    if digits.startswith(cc_digits) and 11 <= len(digits) <= 15:
        return f"+{digits}"
    if 7 <= len(digits) <= 12:
        return f"{default_cc}{digits}"
    return None


def normalize_channel(value, value_map: dict | None = None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "whatsapp"
    s = str(value).strip().lower()
    if value_map:
        # LLM-proposed mapping first (keys may be in original casing)
        for k, v in value_map.items():
            if str(k).strip().lower() == s:
                return v if v in ("whatsapp", "sms", "email", "rcs") else "whatsapp"
    return CHANNEL_SYNONYMS.get(s, "whatsapp")


def normalize_status(value, value_map: dict | None = None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "completed"
    s = str(value).strip().lower()
    if value_map:
        for k, v in value_map.items():
            if str(k).strip().lower() == s:
                return v if v in ("completed", "returned", "cancelled") else "completed"
    return STATUS_SYNONYMS.get(s, "completed")


def normalize_amount(value) -> float | None:
    """Strip currency symbols/commas: '₹1,299.00' -> 1299.0"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = re.sub(r"[^\d.\-]", "", str(value))
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def normalize_date(value) -> str | None:
    """Parse flexible date formats to ISO 8601."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(str(value), errors="coerce", dayfirst=False)
    if pd.isna(ts):
        ts = pd.to_datetime(str(value), errors="coerce", dayfirst=True)
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.isoformat()


def split_full_name(value) -> tuple[str, str | None]:
    parts = str(value).strip().split()
    if not parts:
        return "", None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


# ── Mapping application ──────────────────────────────────────────────────────

def apply_mapping(df: pd.DataFrame, analysis: dict) -> pd.DataFrame:
    """
    Rename source columns to canonical fields per the AI mapping and
    normalise all values. Returns a canonical dataframe ready for ingestion.
    """
    entity = analysis.get("entity_type", "customers")
    mapping: dict = analysis.get("mapping", {}) or {}
    value_mappings: dict = analysis.get("value_mappings", {}) or {}
    default_cc: str = analysis.get("default_country_code") or "+91"

    valid_fields = CUSTOMER_FIELDS if entity == "customers" else ORDER_FIELDS

    # Keep only mapped columns; rename source -> canonical
    rename = {src: dst for src, dst in mapping.items() if src in df.columns and dst in valid_fields}
    out = df[list(rename.keys())].rename(columns=rename).copy()

    # Two source columns may map to the same canonical field — keep the first
    out = out.loc[:, ~out.columns.duplicated()]

    if entity == "customers":
        if "first_name" in out.columns:
            # A full-name column mapped to first_name → split it
            names = out["first_name"].apply(split_full_name)
            out["first_name"] = names.apply(lambda t: t[0])
            if "last_name" not in out.columns:
                out["last_name"] = names.apply(lambda t: t[1])
        if "phone" in out.columns:
            out["phone"] = out["phone"].apply(lambda v: normalize_phone(v, default_cc))
        if "email" in out.columns:
            out["email"] = out["email"].apply(
                lambda v: str(v).strip().lower() if pd.notna(v) and str(v).strip() else None
            )
        if "channel_pref" in out.columns:
            cmap = value_mappings.get("channel_pref")
            out["channel_pref"] = out["channel_pref"].apply(lambda v: normalize_channel(v, cmap))
        if "external_id" in out.columns:
            out["external_id"] = out["external_id"].apply(
                lambda v: str(v).strip() if pd.notna(v) and str(v).strip() else None
            )
        if "city" in out.columns:
            out["city"] = out["city"].apply(
                lambda v: str(v).strip().title() if pd.notna(v) and str(v).strip() else None
            )

    else:  # orders
        if "order_date" in out.columns:
            out["order_date"] = out["order_date"].apply(normalize_date)
        if "amount" in out.columns:
            out["amount"] = out["amount"].apply(normalize_amount)
        if "status" in out.columns:
            smap = value_mappings.get("status")
            out["status"] = out["status"].apply(lambda v: normalize_status(v, smap))
        else:
            out["status"] = "completed"
        if "customer_ref" in out.columns:
            ref_type = analysis.get("customer_ref_type") or "external_id"
            if ref_type == "phone":
                out["customer_ref"] = out["customer_ref"].apply(lambda v: normalize_phone(v, default_cc))
            elif ref_type == "email":
                out["customer_ref"] = out["customer_ref"].apply(
                    lambda v: str(v).strip().lower() if pd.notna(v) else None
                )
            else:
                out["customer_ref"] = out["customer_ref"].apply(
                    lambda v: str(v).strip() if pd.notna(v) else None
                )

    return out
