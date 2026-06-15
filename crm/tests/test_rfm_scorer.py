"""
Tests for the RFM scorer.
"""

import pandas as pd
import pytest

from services.rfm_scorer import compute_rfm_scores


@pytest.fixture()
def sample_data():
    customers = pd.DataFrame([{"id": f"c{i}"} for i in range(10)])
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    orders = []
    for i, row in customers.iterrows():
        for j in range(1, 6):
            orders.append(
                {
                    "id": f"o{i}{j}",
                    "customer_id": row["id"],
                    "order_date": (now - timedelta(days=j * 10 + i * 5)).isoformat(),
                    "amount": 1000 + i * 100,
                    "category": "skincare",
                    "product_name": "Rose Serum",
                    "status": "completed",
                }
            )
    return customers, pd.DataFrame(orders)


def test_rfm_scores_shape(sample_data):
    customers, orders = sample_data
    result = compute_rfm_scores(customers, orders)
    assert len(result) == len(customers)
    assert "rfm_score" in result.columns
    assert "churn_risk" in result.columns


def test_churn_risk_values(sample_data):
    customers, orders = sample_data
    result = compute_rfm_scores(customers, orders)
    valid_risks = {"low", "medium", "high", "critical"}
    assert set(result["churn_risk"].unique()).issubset(valid_risks)


def test_rfm_score_range(sample_data):
    customers, orders = sample_data
    result = compute_rfm_scores(customers, orders)
    assert result["rfm_score"].between(0, 100).all()


def test_rfm_scorer_small_dataset():
    """Verify that rfm scorer does not raise error on small datasets (< 5 elements)."""
    customers = pd.DataFrame([{"id": "c1"}, {"id": "c2"}])
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    orders = pd.DataFrame([
        {
            "id": "o1",
            "customer_id": "c1",
            "order_date": now.isoformat(),
            "amount": 500.0,
            "category": "skincare",
            "product_name": "Moisturizer",
            "status": "completed"
        },
        {
            "id": "o2",
            "customer_id": "c2",
            "order_date": now.isoformat(),
            "amount": 1500.0,
            "category": "haircare",
            "product_name": "Shampoo",
            "status": "completed"
        }
    ])
    result = compute_rfm_scores(customers, orders)
    assert len(result) == 2
    assert "rfm_score" in result.columns
    assert result["rfm_score"].between(0, 100).all()

