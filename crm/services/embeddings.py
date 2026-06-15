"""
Embedding service — local ONNX text embeddings for the RAG / vector layer.

Uses fastembed (BAAI/bge-small-en-v1.5, 384-dim) which runs on CPU with no
external API — ideal for real-time, low-cost deployment. Each customer is
rendered into a short natural-language "profile document" that captures their
behaviour semantically, then embedded and stored in Supabase pgvector.
"""

from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

# Persist the model next to the repo so it isn't re-downloaded from temp.
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".model_cache")

_model = None
_lock = Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
                from fastembed import TextEmbedding
                logger.info("Loading embedding model %s ...", EMBED_MODEL)
                _model = TextEmbedding(EMBED_MODEL, cache_dir=_CACHE_DIR)
    return _model


# ── Document construction ─────────────────────────────────────────────────────

def _band(value: Optional[float], buckets: list[tuple[float, str]]) -> str:
    if value is None:
        return "unknown"
    for threshold, label in buckets:
        if value <= threshold:
            return label
    return buckets[-1][1]


def customer_document(customer: dict, score: Optional[dict] = None) -> str:
    """
    Render a customer + RFM score into a natural-language profile document.
    This is what gets embedded — phrase it so semantics (intent, value, loyalty,
    category affinity) are captured, not just keywords.
    """
    score = score or {}
    name = f"{customer.get('first_name', '')} {customer.get('last_name', '') or ''}".strip()
    city = customer.get("city") or "unknown city"
    channel = customer.get("channel_pref") or "whatsapp"
    top_cat = score.get("top_category") or "various"
    last_product = score.get("last_product") or "various products"
    churn = score.get("churn_risk") or "unknown"
    freq = score.get("frequency")
    monetary = score.get("monetary")
    recency = score.get("recency_days")

    loyalty = _band(freq if freq is not None else None, [(1, "one-time buyer"), (4, "occasional buyer"),
                                                         (9, "repeat buyer"), (1e9, "loyal frequent buyer")])
    value = _band(float(monetary) if monetary is not None else None,
                  [(2000, "low spender"), (8000, "mid-value customer"),
                   (20000, "high-value customer"), (1e12, "VIP big spender")])
    activity = _band(float(recency) if recency is not None else None,
                     [(30, "recently active"), (60, "slightly lapsed"),
                      (90, "lapsed"), (1e9, "long dormant")])

    return (
        f"{name} from {city} is a {value}, {loyalty}, {activity} with {churn} churn risk. "
        f"They mainly buy {top_cat} products and last purchased {last_product}. "
        f"They prefer being contacted on {channel}. "
        f"Lifetime spend around {int(monetary) if monetary else 0} rupees over {freq or 0} orders, "
        f"last order {recency if recency is not None else 'unknown'} days ago."
    )


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts -> list of 384-d float vectors."""
    if not texts:
        return []
    model = _get_model()
    return [vec.tolist() for vec in model.embed(texts)]


def embed_query(query: str) -> list[float]:
    """Embed a single search query."""
    return embed_texts([query])[0]


def to_pgvector(vec: Iterable[float]) -> str:
    """Format a vector as a pgvector text literal: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
