"""
Customer embedder — builds + stores pgvector embeddings for customers.

Pulls a customer's RFM score to enrich the profile document, embeds it, and
writes customers.embedding. Used by the backfill script and on create/import.
Failures are swallowed so the core CRUD path never breaks if embeddings are
unavailable (e.g. model still downloading).
"""

from __future__ import annotations

import logging

from config import supabase
from services.embeddings import customer_document, embed_texts, to_pgvector

logger = logging.getLogger(__name__)


def embed_customer_ids(customer_ids: list[str]) -> int:
    """Embed + store vectors for the given customer ids. Returns count embedded."""
    if not customer_ids:
        return 0

    embedded = 0
    chunk = 100
    for i in range(0, len(customer_ids), chunk):
        ids = customer_ids[i : i + chunk]
        rows = (
            supabase.table("customers")
            .select("id, first_name, last_name, city, channel_pref, score:customer_scores(*)")
            .in_("id", ids)
            .execute()
        ).data or []

        docs, doc_ids = [], []
        for r in rows:
            score = r.get("score")
            if isinstance(score, list):
                score = score[0] if score else {}
            docs.append(customer_document(r, score or {}))
            doc_ids.append(r["id"])

        if not docs:
            continue
        vectors = embed_texts(docs)
        for cid, vec in zip(doc_ids, vectors):
            supabase.table("customers").update({"embedding": to_pgvector(vec)}).eq("id", cid).execute()
            embedded += 1

    return embedded


def safe_embed_async(customer_ids: list[str]) -> None:
    """Fire-and-forget embedding in a background thread (never blocks the request)."""
    if not customer_ids:
        return
    import threading

    def _run():
        try:
            n = embed_customer_ids(customer_ids)
            logger.info("Embedded %d customers for semantic search.", n)
        except Exception as e:  # noqa: BLE001
            logger.warning("Customer embedding failed (non-fatal): %s", e)

    threading.Thread(target=_run, daemon=True).start()
