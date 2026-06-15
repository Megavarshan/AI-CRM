"""
Backfill — create the Demo organization and assign all pre-existing
(org-less) data to it. Run AFTER applying migration 003.

    cd crm && python db/backfill_demo_org.py

Idempotent: re-running only fills rows whose org_id is still NULL.
The Demo org is a real login so the sample data stays explorable:
    Org ID:   ORB-DEMO01
    Password: demo1234
"""

from __future__ import annotations

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import supabase  # noqa: E402
from routers.auth import hash_password  # noqa: E402

DEMO_ORG_ID = "ORB-DEMO01"
DEMO_PASSWORD = "demo1234"


def ensure_demo_org() -> str:
    existing = supabase.table("organizations").select("id").eq("org_id", DEMO_ORG_ID).execute()
    if existing.data:
        print(f"Demo org already exists: {existing.data[0]['id']}")
        return existing.data[0]["id"]

    payload = {
        "org_id": DEMO_ORG_ID,
        "company_name": "Demo Brand (Orbit Sample)",
        "customer_size": "10k-100k",
        "turnover": "Sample data",
        "city": "Mumbai",
        "country": "India",
        "website": "https://orbit.demo",
        "password_hash": hash_password(DEMO_PASSWORD),
    }
    res = supabase.table("organizations").insert(payload).execute()
    org_uuid = res.data[0]["id"]
    print(f"Created Demo org {DEMO_ORG_ID} -> {org_uuid}  (login: {DEMO_ORG_ID} / {DEMO_PASSWORD})")
    return org_uuid


def backfill(table: str, org_uuid: str) -> None:
    res = supabase.table(table).update({"org_id": org_uuid}).is_("org_id", "null").execute()
    print(f"  {table}: assigned org_id to {len(res.data or [])} rows")


def main() -> None:
    org_uuid = ensure_demo_org()
    for table in ("customers", "orders", "segments", "campaigns", "communications"):
        try:
            backfill(table, org_uuid)
        except Exception as e:
            print(f"  {table}: skipped ({e})")
    print("Backfill complete.")


if __name__ == "__main__":
    main()
