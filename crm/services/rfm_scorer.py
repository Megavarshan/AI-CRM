"""
RFM Scorer — computes Recency, Frequency, Monetary scores for customers.

Uses pandas for in-memory computation. Efficient up to ~1M customers.
Provides robust safety fallbacks for small datasets (fewer than 5 customers)
and highly skewed purchase distributions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def safe_qcut(series: pd.Series, labels: list[int]) -> pd.Series:
    """
    Perform quantile-based binning safely.
    Handles small datasets (N < len(labels)) and duplicate bin edges
    by ranking values prior to binning.
    """
    n = len(series)
    if n == 0:
        return pd.Series(dtype=float)

    is_reversed = labels[0] > labels[-1]
    target_labels = labels if not is_reversed else list(reversed(labels))

    if n < len(labels):
        # Small dataset fallback: assign scores linearly based on rank
        ranks = series.rank(method="first", ascending=True)
        # Scale rank to the index of labels
        if n > 1:
            scaled = 1 + (ranks - 1) * (len(target_labels) - 1) / (n - 1)
            scores = scaled.round().astype(int)
        else:
            scores = pd.Series([target_labels[-1]] * n, index=series.index)

        if is_reversed:
            # Reverse scores back
            scores = len(labels) + 1 - scores
        return scores

    try:
        # Rank values with method="first" to ensure unique values for qcut
        ranks = series.rank(method="first", ascending=True)
        return pd.qcut(ranks, len(labels), labels=labels)
    except Exception:
        # Fallback to rank scaling if qcut fails for any reason
        ranks = series.rank(method="first", ascending=True)
        scaled = 1 + (ranks - 1) * (len(target_labels) - 1) / (n - 1)
        scores = scaled.round().astype(int)
        if is_reversed:
            scores = len(labels) + 1 - scores
        return scores


def compute_rfm_scores(
    df_customers: pd.DataFrame,
    df_orders: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute RFM scores for all customers.

    Parameters
    ----------
    df_customers : DataFrame with at least columns [id]
    df_orders    : DataFrame with columns [customer_id, order_date, amount,
                   category, product_name, status]

    Returns
    -------
    DataFrame with columns:
        customer_id, recency_days, frequency, monetary, rfm_score,
        churn_risk, top_category, last_product, scored_at
    """
    today = pd.Timestamp.utcnow()

    # Only completed orders contribute to RFM
    completed = df_orders[df_orders["status"] == "completed"].copy()

    if completed.empty or df_customers.empty:
        return pd.DataFrame()

    # Group by customer and compute raw aggregates
    agg_spec = dict(
        last_order_date=("order_date", "max"),
        frequency=("id", "count"),
        monetary=("amount", "sum"),
        top_category=("category", lambda x: x.value_counts().index[0] if len(x) > 0 else None),
        last_product=("product_name", "last"),
    )
    # Carry org_id through for multi-tenant scoping (if present on orders).
    if "org_id" in completed.columns:
        agg_spec["org_id"] = ("org_id", "first")

    agg = completed.groupby("customer_id").agg(**agg_spec).reset_index()

    agg["order_date"] = pd.to_datetime(agg["last_order_date"], utc=True)
    agg["recency_days"] = (today - agg["order_date"]).dt.days

    # Score each dimension 1–5 using safe quantile binning
    agg["r_score"] = safe_qcut(agg["recency_days"], [5, 4, 3, 2, 1])
    agg["f_score"] = safe_qcut(agg["frequency"], [1, 2, 3, 4, 5])
    agg["m_score"] = safe_qcut(agg["monetary"], [1, 2, 3, 4, 5])

    # Convert scores to float for composite calculation
    agg["r_score"] = agg["r_score"].astype(float)
    agg["f_score"] = agg["f_score"].astype(float)
    agg["m_score"] = agg["m_score"].astype(float)

    # Composite RFM Score = (R*0.4 + F*0.3 + M*0.3) * 20 (scales to 0–100)
    agg["rfm_score"] = (
        agg["r_score"] * 0.4
        + agg["f_score"] * 0.3
        + agg["m_score"] * 0.3
    ) * 20

    # Classify churn risk
    agg["churn_risk"] = agg.apply(_churn_bucket, axis=1)
    agg["scored_at"] = today

    cols = [
        "customer_id",
        "recency_days",
        "frequency",
        "monetary",
        "rfm_score",
        "churn_risk",
        "top_category",
        "last_product",
        "scored_at",
    ]
    if "org_id" in agg.columns:
        cols.append("org_id")
    result = agg[cols].copy()
    if "org_id" in result.columns:
        result["org_id"] = result["org_id"].apply(lambda x: x if pd.notna(x) else None)

    # Coerce numpy / pandas scalar types to JSON-serialisable native Python types.
    # Without this, supabase-py's json.dumps() chokes on np.int64 / np.float64 /
    # pd.Timestamp / NaN when upserting into customer_scores.
    result["recency_days"] = result["recency_days"].apply(lambda x: int(x) if pd.notna(x) else None)
    result["frequency"] = result["frequency"].apply(lambda x: int(x) if pd.notna(x) else None)
    result["monetary"] = result["monetary"].apply(lambda x: round(float(x), 2) if pd.notna(x) else None)
    result["rfm_score"] = result["rfm_score"].apply(lambda x: round(float(x), 2) if pd.notna(x) else None)
    result["top_category"] = result["top_category"].apply(lambda x: x if pd.notna(x) else None)
    result["last_product"] = result["last_product"].apply(lambda x: x if pd.notna(x) else None)
    result["scored_at"] = result["scored_at"].apply(
        lambda x: x.isoformat() if hasattr(x, "isoformat") else x
    )

    return result


def _churn_bucket(row: pd.Series) -> str:
    """Map RFM metrics to a churn risk tier."""
    if pd.isna(row["recency_days"]) or pd.isna(row["rfm_score"]):
        return "critical"
    
    if row["recency_days"] > 90 or row["rfm_score"] < 20:
        return "critical"
    elif row["recency_days"] > 60 or row["rfm_score"] < 40:
        return "high"
    elif row["recency_days"] > 30 or row["rfm_score"] < 60:
        return "medium"
    return "low"
