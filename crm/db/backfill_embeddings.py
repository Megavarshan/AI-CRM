"""
Backfill — embed all existing customers into pgvector for semantic search.

Run AFTER applying migration 004:
    cd crm && python db/backfill_embeddings.py

Re-running only embeds customers whose embedding is still NULL (pass --all to redo).
"""

from __future__ import annotations

import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import supabase  # noqa: E402
from services.customer_embedder import embed_customer_ids  # noqa: E402


def fetch_ids(only_missing: bool) -> list[str]:
    ids: list[str] = []
    offset, chunk = 0, 1000
    while True:
        q = supabase.table("customers").select("id, embedding")
        res = q.range(offset, offset + chunk - 1).execute()
        if not res.data:
            break
        for r in res.data:
            if not only_missing or r.get("embedding") is None:
                ids.append(r["id"])
        if len(res.data) < chunk:
            break
        offset += chunk
    return ids


def main() -> None:
    only_missing = "--all" not in sys.argv
    ids = fetch_ids(only_missing)
    print(f"Embedding {len(ids)} customers ({'missing only' if only_missing else 'ALL'})...")
    t = time.time()
    n = embed_customer_ids(ids)
    print(f"Done. Embedded {n} customers in {time.time() - t:.1f}s.")
    print("Tip: run `ANALYZE customers;` in SQL editor for best ivfflat recall.")


if __name__ == "__main__":
    main()
