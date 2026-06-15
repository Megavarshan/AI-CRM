"""
Unit tests for CRM Customer and Order router endpoints.
Mocks the Supabase and Redis client requests.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from uuid import uuid4

from main import app

client = TestClient(app)


@pytest.fixture
def mock_supabase():
    with patch("routers.customers.supabase") as mock_db, patch("routers.orders.supabase") as mock_db_orders:
        yield mock_db, mock_db_orders


@pytest.fixture
def mock_redis():
    with patch("routers.customers.redis_client") as mock_cache:
        yield mock_cache


def test_list_customers_success(mock_supabase):
    mock_db, _ = mock_supabase
    
    # Mock return data
    mock_execute = MagicMock()
    mock_execute.data = [
        {
            "id": str(uuid4()),
            "first_name": "Aarav",
            "last_name": "Patel",
            "phone": "+919000000001",
            "email": "aarav@example.com",
            "city": "Mumbai",
            "channel_pref": "whatsapp",
            "score": [
                {
                    "recency_days": 10,
                    "frequency": 3,
                    "monetary": 4500.0,
                    "rfm_score": 85.0,
                    "churn_risk": "low",
                }
            ]
        }
    ]
    mock_execute.count = 1

    # Chain mock setup
    mock_db.table.return_value.select.return_value.or_.return_value.order.return_value.range.return_value.execute.return_value = mock_execute
    # For no search/sort parameters:
    mock_db.table.return_value.select.return_value.order.return_value.range.return_value.execute.return_value = mock_execute

    resp = client.get("/api/v1/customers?page=1&limit=10")
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["total"] == 1
    assert res_json["data"][0]["first_name"] == "Aarav"
    assert res_json["data"][0]["score"]["churn_risk"] == "low"


def test_get_customer_not_found(mock_supabase):
    mock_db, _ = mock_supabase
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    cust_id = str(uuid4())
    resp = client.get(f"/api/v1/customers/{cust_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Customer not found"


def test_create_customer_success(mock_supabase):
    _, mock_db_orders = mock_supabase
    
    # Let's mock the uniqueness check checks inside routers.customers.supabase
    with patch("routers.customers.supabase") as mock_cust_db, \
         patch("tasks.score_customers.score_single_customer.delay") as mock_celery:
         
        # Mock phone search
        mock_cust_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        
        # Mock insert response
        new_cust_id = str(uuid4())
        mock_insert_res = MagicMock()
        mock_insert_res.data = [{
            "id": new_cust_id,
            "first_name": "Neha",
            "phone": "+919876543211",
            "channel_pref": "sms",
            "created_at": "2026-06-12T00:00:00Z",
            "updated_at": "2026-06-12T00:00:00Z"
        }]
        mock_cust_db.table.return_value.insert.return_value.execute.return_value = mock_insert_res

        payload = {
            "first_name": "Neha",
            "phone": "+919876543211",
            "channel_pref": "sms"
        }
        resp = client.post("/api/v1/customers", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"] == new_cust_id
        mock_celery.assert_called_once_with(new_cust_id)


def test_create_order_customer_not_found(mock_supabase):
    _, mock_db_orders = mock_supabase
    # Mock customer check returned empty
    mock_db_orders.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    order_payload = {
        "customer_id": str(uuid4()),
        "order_date": "2026-06-12T12:00:00Z",
        "amount": 2500.0,
        "category": "haircare",
        "product_name": "Argan Oil Shampoo"
    }
    resp = client.post("/api/v1/orders", json=order_payload)
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]


@patch("routers.segments.supabase")
def test_list_segments(mock_seg_db):
    mock_execute = MagicMock()
    mock_execute.data = [{
        "id": str(uuid4()),
        "name": "High value",
        "description": "Spent > 5000",
        "filter_spec": {"operator": "AND", "conditions": []},
        "nl_query": None,
        "customer_count": 10,
        "created_at": "2026-06-12T00:00:00Z",
        "updated_at": "2026-06-12T00:00:00Z"
    }]
    mock_seg_db.table.return_value.select.return_value.order.return_value.execute.return_value = mock_execute

    resp = client.get("/api/v1/segments")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "High value"


@patch("routers.segments.supabase")
@patch("services.segment_executor.supabase")
def test_create_segment(mock_exec_db, mock_seg_db):
    # Mock execute_filter_spec call (returns count, preview)
    mock_exec_execute = MagicMock()
    mock_exec_execute.count = 5
    mock_exec_execute.data = []
    mock_exec_db.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_exec_execute

    # Mock insert segment
    new_seg_id = str(uuid4())
    mock_seg_execute = MagicMock()
    mock_seg_execute.data = [{
        "id": new_seg_id,
        "name": "High value",
        "description": "Spent > 5000",
        "filter_spec": {"operator": "AND", "conditions": [{"field": "monetary", "op": "gte", "value": 5000}]},
        "nl_query": None,
        "customer_count": 5,
        "created_at": "2026-06-12T00:00:00Z",
        "updated_at": "2026-06-12T00:00:00Z"
    }]
    mock_seg_db.table.return_value.insert.return_value.execute.return_value = mock_seg_execute

    payload = {
        "name": "High value",
        "description": "Spent > 5000",
        "filter_spec": {"operator": "AND", "conditions": [{"field": "monetary", "op": "gte", "value": 5000}]}
    }
    resp = client.post("/api/v1/segments", json=payload)
    assert resp.status_code == 201
    assert resp.json()["id"] == new_seg_id
    assert resp.json()["customer_count"] == 5


@patch("routers.segments.supabase")
@patch("services.segment_executor.supabase")
@patch("services.ai_engine.nl_to_segment")
def test_nl_to_segment(mock_nl_call, mock_exec_db, mock_seg_db):
    mock_nl_call.return_value = {
        "operator": "AND",
        "conditions": [{"field": "monetary", "op": "gte", "value": 5000}]
    }

    mock_exec_execute = MagicMock()
    mock_exec_execute.count = 2
    mock_exec_execute.data = [
        {"first_name": "Priya", "last_name": "Sharma", "score": []},
        {"first_name": "Rahul", "last_name": "Mehta", "score": []}
    ]
    mock_exec_db.table.return_value.select.return_value.filter.return_value.limit.return_value.execute.return_value = mock_exec_execute

    payload = {"query": "customers who spent over 5000 rupees"}
    resp = client.post("/api/v1/segments/nl2segment", json=payload)
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["customer_count"] == 2
    assert "Priya Sharma" in res_json["preview"]

