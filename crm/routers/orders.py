"""
CRM router — Orders.

Endpoints:
  POST /orders       — create single order
  POST /orders/bulk  — create multiple orders
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from config import supabase
from deps import OrgContext, get_org
from models.order import OrderBulkCreate, OrderCreate, OrderRead

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(body: OrderCreate, org: OrgContext = Depends(get_org)):
    """Create a single order and re-score the customer's RFM."""
    # mode="json" serialises UUID -> str and datetime -> ISO string.
    payload = org.stamp(body.model_dump(mode="json"))

    try:
        # Verify customer exists in this org prior to order creation
        cust_check = org.scope(
            supabase.table("customers").select("id").eq("id", str(payload["customer_id"]))
        ).execute()
        if not cust_check.data:
            raise HTTPException(
                status_code=400,
                detail=f"Customer with ID {payload['customer_id']} does not exist.",
            )

        res = supabase.table("orders").insert(payload).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to write order record.")

        new_order = res.data[0]

        # Trigger RFM scoring asynchronously for the affected customer
        from tasks.score_customers import score_single_customer
        score_single_customer.delay(str(new_order["customer_id"]))

        return new_order

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/bulk", response_model=list[OrderRead], status_code=status.HTTP_201_CREATED)
async def create_orders_bulk(body: OrderBulkCreate, org: OrgContext = Depends(get_org)):
    """Create multiple orders in one call."""
    if not body.orders:
        return []

    payloads = []
    customer_ids = set()
    for o in body.orders:
        row = org.stamp(o.model_dump(mode="json"))
        payloads.append(row)
        customer_ids.add(str(row["customer_id"]))

    try:
        # Check all customer IDs belong to this org
        cust_ids_list = list(customer_ids)
        cust_check = org.scope(
            supabase.table("customers").select("id").in_("id", cust_ids_list)
        ).execute()
        existing_cust_ids = {c["id"] for c in cust_check.data}

        # Return 400 if any referenced customer is missing
        for cid in cust_ids_list:
            if cid not in existing_cust_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Customer with ID '{cid}' does not exist.",
                )

        # Insert orders in chunks of 200
        chunk_size = 200
        inserted_orders = []
        for i in range(0, len(payloads), chunk_size):
            chunk = payloads[i : i + chunk_size]
            res = supabase.table("orders").insert(chunk).execute()
            inserted_orders.extend(res.data)

        # Batch-trigger scoring for all modified customers
        if customer_ids:
            from tasks.score_customers import batch_score_customers
            batch_score_customers.delay(list(customer_ids))

        return inserted_orders

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk importing orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))
