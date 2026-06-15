"""
Unit tests for campaign and receipt router endpoints.
Mocks Supabase database calls and Celery task delays.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from uuid import uuid4

from main import app

client = TestClient(app)


@pytest.fixture
def mock_supabase():
    with patch("routers.campaigns.supabase") as mock_db, \
         patch("routers.receipts.supabase") as mock_receipts_db:
        yield mock_db, mock_receipts_db


def test_list_campaigns(mock_supabase):
    mock_db, _ = mock_supabase
    
    mock_execute = MagicMock()
    mock_execute.data = [{
        "id": str(uuid4()),
        "name": "Diwali campaign",
        "segment_id": str(uuid4()),
        "channel": "whatsapp",
        "message_template": "Hey {first_name}!",
        "status": "draft",
        "total_sent": 0,
        "total_delivered": 0,
        "total_opened": 0,
        "total_clicked": 0,
        "total_failed": 0,
        "created_at": "2026-06-12T00:00:00Z",
        "updated_at": "2026-06-12T00:00:00Z"
    }]
    mock_db.table.return_value.select.return_value.order.return_value.range.return_value.execute.return_value = mock_execute

    resp = client.get("/api/v1/campaigns")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Diwali campaign"


def test_create_campaign_success(mock_supabase):
    mock_db, _ = mock_supabase

    # Mock segment validation check (segment exists)
    mock_seg_execute = MagicMock()
    mock_seg_execute.data = [{"id": str(uuid4())}]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_seg_execute

    # Mock insert
    new_camp_id = str(uuid4())
    mock_insert_execute = MagicMock()
    mock_insert_execute.data = [{
        "id": new_camp_id,
        "name": "Diwali Promo",
        "segment_id": str(uuid4()),
        "channel": "whatsapp",
        "message_template": "Hey {first_name}!",
        "status": "draft",
        "total_sent": 0,
        "total_delivered": 0,
        "total_opened": 0,
        "total_clicked": 0,
        "total_failed": 0,
        "created_at": "2026-06-12T00:00:00Z",
        "updated_at": "2026-06-12T00:00:00Z"
    }]
    mock_db.table.return_value.insert.return_value.execute.return_value = mock_insert_execute

    payload = {
        "name": "Diwali Promo",
        "segment_id": str(uuid4()),
        "channel": "whatsapp",
        "message_template": "Hey {first_name}!"
    }
    resp = client.post("/api/v1/campaigns", json=payload)
    assert resp.status_code == 201
    assert resp.json()["id"] == new_camp_id
    assert resp.json()["status"] == "draft"


def test_launch_campaign_success(mock_supabase):
    mock_db, _ = mock_supabase

    camp_id = str(uuid4())
    # Mock campaign fetch (in draft)
    mock_execute = MagicMock()
    mock_execute.data = [{
        "id": camp_id,
        "name": "Diwali Promo",
        "segment_id": str(uuid4()),
        "channel": "whatsapp",
        "status": "draft",
        "message_template": "Hey {first_name}!"
    }]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute
    
    # Mock update status
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    with patch("tasks.campaigns.launch_campaign_task.delay") as mock_celery:
        resp = client.post(f"/api/v1/campaigns/{camp_id}/launch")
        assert resp.status_code == 202
        assert resp.json()["status"] == "running"
        mock_celery.assert_called_once_with(camp_id)


def test_ingest_receipt_success(mock_supabase):
    _, mock_receipts_db = mock_supabase

    comm_id = str(uuid4())
    camp_id = str(uuid4())

    # Mock communication check (status queued, timestamp delivered_at is None)
    mock_comm_execute = MagicMock()
    mock_comm_execute.data = [{
        "id": comm_id,
        "campaign_id": camp_id,
        "customer_id": str(uuid4()),
        "channel": "whatsapp",
        "personalized_message": "Hello Priya",
        "status": "queued",
        "delivered_at": None
    }]
    mock_receipts_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_comm_execute

    # Mock update and RPC increment calls
    mock_receipts_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    mock_receipts_db.rpc.return_value.execute.return_value = MagicMock()

    # Mock campaign complete check (not completed yet: total_resolved < total_sent)
    mock_camp_execute = MagicMock()
    mock_camp_execute.data = [{
        "status": "running",
        "total_sent": 10,
        "total_delivered": 5,
        "total_failed": 0
    }]
    mock_receipts_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_camp_execute

    payload = {
        "communication_id": comm_id,
        "campaign_id": camp_id,
        "idempotency_key": f"key_delivered",
        "status": "delivered",
        "timestamp": "2026-06-12T12:00:00Z"
    }
    resp = client.post("/api/v1/receipts", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
