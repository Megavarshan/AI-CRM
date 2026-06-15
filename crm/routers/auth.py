"""
CRM router — Authentication.

Endpoints:
  POST /auth/org/signup   — register an organization, auto-generate org_id
  POST /auth/org/login    — org_id + password
  POST /auth/admin/login  — fixed admin credentials (demo)

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib, no extra deps).
Sessions are client-side (localStorage) — this is a demo-grade auth layer,
not production RBAC. See README §15 scale notes.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from config import supabase

logger = logging.getLogger(__name__)

router = APIRouter()

PBKDF2_ITERATIONS = 200_000

# Demo admin credentials (per spec: both "admin")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"


# ── Password hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return secrets.compare_digest(candidate, digest)
    except (ValueError, AttributeError):
        return False


def generate_org_id() -> str:
    """Human-friendly org ID like ORB-7F3K2A (unambiguous charset)."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no I/L/O/0/1
    return "ORB-" + "".join(secrets.choice(alphabet) for _ in range(6))


# ── Models ───────────────────────────────────────────────────────────────────

class OrgSignup(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=120)
    customer_size: Optional[str] = None
    turnover: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    password: str = Field(..., min_length=6, max_length=128)


class OrgLogin(BaseModel):
    org_id: str
    password: str


class AdminLogin(BaseModel):
    username: str
    password: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/auth/org/signup", status_code=status.HTTP_201_CREATED)
async def org_signup(body: OrgSignup):
    """Register a new organization and return its generated org_id."""
    try:
        # Generate a unique org_id (retry on the rare collision)
        org_id = generate_org_id()
        for _ in range(5):
            existing = supabase.table("organizations").select("id").eq("org_id", org_id).execute()
            if not existing.data:
                break
            org_id = generate_org_id()

        payload = {
            "org_id": org_id,
            "company_name": body.company_name.strip(),
            "customer_size": body.customer_size,
            "turnover": body.turnover,
            "city": body.city,
            "country": body.country,
            "website": body.website,
            "password_hash": hash_password(body.password),
        }
        res = supabase.table("organizations").insert(payload).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create organization.")

        org = res.data[0]
        return {
            "org_id": org["org_id"],
            "company_name": org["company_name"],
            "message": f"Organization registered. Your login ID is {org['org_id']} — save it!",
        }

    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "organizations" in msg and ("PGRST205" in msg or "schema cache" in msg):
            raise HTTPException(
                status_code=503,
                detail="The organizations table is missing. Run crm/db/migrations/002_organizations.sql in the Supabase SQL Editor.",
            )
        logger.error(f"Org signup failed: {e}")
        raise HTTPException(status_code=500, detail=msg)


@router.post("/auth/org/login")
async def org_login(body: OrgLogin):
    """Authenticate an organization by org_id + password."""
    try:
        res = (
            supabase.table("organizations")
            .select("*")
            .eq("org_id", body.org_id.strip().upper())
            .execute()
        )
        if not res.data or not verify_password(body.password, res.data[0]["password_hash"]):
            # Same message for unknown org / wrong password (no user enumeration)
            raise HTTPException(status_code=401, detail="Invalid org ID or password.")

        org = res.data[0]
        supabase.table("organizations").update(
            {"last_login_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", org["id"]).execute()

        return {
            "role": "organization",
            "org_id": org["org_id"],
            "org_uuid": org["id"],          # used as X-Org-Id for data scoping
            "company_name": org["company_name"],
            "city": org.get("city"),
            "country": org.get("country"),
            "website": org.get("website"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Org login failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/admin/login")
async def admin_login(body: AdminLogin):
    """Authenticate the platform admin (fixed demo credentials)."""
    if body.username == ADMIN_USERNAME and body.password == ADMIN_PASSWORD:
        return {"role": "admin", "username": "admin", "company_name": "Orbit Platform Admin"}
    raise HTTPException(status_code=401, detail="Invalid admin credentials.")
