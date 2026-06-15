"""
Shared FastAPI dependencies — multi-tenant org scoping.

The frontend sends the authenticated org's UUID in the `X-Org-Id` header
(see lib/api.ts). Organizations are scoped to their own data; the platform
admin sends `X-Org-Id: ALL` and sees everything.

Usage in a router:

    from deps import OrgContext, get_org

    @router.get("/customers")
    async def list_customers(org: OrgContext = Depends(get_org)):
        q = supabase.table("customers").select("*")
        q = org.scope(q)          # adds .eq("org_id", ...) unless admin
        ...
        payload = org.stamp(payload)   # sets org_id on inserts
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Header, HTTPException


@dataclass
class OrgContext:
    """Resolved tenant context for a request."""
    org_id: Optional[str]   # None => admin / platform (no filter)

    @property
    def is_admin(self) -> bool:
        return self.org_id is None

    def scope(self, query: Any) -> Any:
        """Apply the org filter to a PostgREST query (no-op for admin)."""
        if self.org_id is not None:
            return query.eq("org_id", self.org_id)
        return query

    def stamp(self, payload: dict) -> dict:
        """Attach org_id to a row about to be inserted.

        Admin must target a concrete org, so inserts require a real org_id.
        """
        if self.org_id is None:
            raise HTTPException(
                status_code=400,
                detail="Admin must act within a specific organization to create data. "
                       "Provide a concrete X-Org-Id (organization UUID).",
            )
        return {**payload, "org_id": self.org_id}

    def require_org(self) -> str:
        if self.org_id is None:
            raise HTTPException(status_code=400, detail="This action requires an organization context.")
        return self.org_id


async def get_org(x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id")) -> OrgContext:
    """
    Resolve the tenant from the X-Org-Id header.
      - missing or 'ALL'  -> admin (no filter)
      - a UUID            -> that organization
    """
    if not x_org_id or x_org_id.strip().upper() == "ALL":
        return OrgContext(org_id=None)
    return OrgContext(org_id=x_org_id.strip())
