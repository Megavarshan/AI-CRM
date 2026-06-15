"""
Celery tasks for RFM scoring.

Tasks:
  score_single_customer(customer_id) — triggered after order insert / customer create
  batch_score_customers(customer_ids) — triggered after bulk customer import or order bulk uploads
  batch_score_all_customers()        — nightly Celery Beat job (re-calculates everything)
"""

from __future__ import annotations

import logging
import pandas as pd

from celery_app import app
from config import supabase
from services.rfm_scorer import compute_rfm_scores

logger = logging.getLogger(__name__)


def fetch_all_rows(table_name: str, select_fields: str = "*", chunk_size: int = 1000) -> list[dict]:
    """
    Fetch all rows from a Supabase table by paginating via range requests.
    Prevents missing data due to PostgREST's default max row limits (usually 1000).
    """
    offset = 0
    all_data: list[dict] = []
    while True:
        try:
            res = (
                supabase.table(table_name)
                .select(select_fields)
                .range(offset, offset + chunk_size - 1)
                .execute()
            )
            data = res.data
            if not data:
                break
            all_data.extend(data)
            if len(data) < chunk_size:
                break
            offset += chunk_size
        except Exception as e:
            logger.error(f"Error paginating table {table_name} at offset {offset}: {e}")
            raise e
    return all_data


@app.task(name="tasks.score_customers.score_single_customer", bind=True, max_retries=3)
def score_single_customer(self, customer_id: str) -> None:
    """Recompute RFM score for a single customer and upsert into customer_scores."""
    try:
        # Fetch customer + all their orders
        orders_resp = (
            supabase.table("orders")
            .select("*")
            .eq("customer_id", customer_id)
            .execute()
        )
        df_orders = pd.DataFrame(orders_resp.data)
        df_customers = pd.DataFrame([{"id": customer_id}])

        if df_orders.empty:
            logger.info(f"No orders found for customer {customer_id}; skipping scoring.")
            return

        scores = compute_rfm_scores(df_customers, df_orders)
        if scores.empty:
            return

        row = scores.iloc[0].to_dict()
        row["customer_id"] = customer_id

        supabase.table("customer_scores").upsert(row, on_conflict="customer_id").execute()
        logger.info(f"Successfully re-scored customer {customer_id}.")

    except Exception as exc:
        logger.error(f"Failed to score customer {customer_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@app.task(name="tasks.score_customers.batch_score_customers", bind=True, max_retries=3)
def batch_score_customers(self, customer_ids: list[str]) -> None:
    """Recompute RFM scores for a specific list of customers and upsert."""
    if not customer_ids:
        return

    try:
        logger.info(f"Running batch scoring for {len(customer_ids)} customers...")
        
        # Paginated fetch of orders matching the customer list to prevent hitting limits
        # PostgREST allows filtering with in list. We chunk customer_ids if the list is huge.
        orders = []
        cust_chunk_size = 200
        for i in range(0, len(customer_ids), cust_chunk_size):
            chunk_ids = customer_ids[i : i + cust_chunk_size]
            res = (
                supabase.table("orders")
                .select("*")
                .in_("customer_id", chunk_ids)
                .execute()
            )
            if res.data:
                orders.extend(res.data)

        df_orders = pd.DataFrame(orders)
        df_customers = pd.DataFrame([{"id": cid} for cid in customer_ids])

        if df_orders.empty:
            logger.info("No completed orders found for the imported customer batch.")
            return

        scores = compute_rfm_scores(df_customers, df_orders)
        if scores.empty:
            return

        rows = scores.to_dict(orient="records")
        supabase.table("customer_scores").upsert(rows, on_conflict="customer_id").execute()
        logger.info(f"Successfully batch scored {len(rows)} customers.")

    except Exception as exc:
        logger.error(f"Failed batch scoring customers: {exc}")
        raise self.retry(exc=exc, countdown=30)


@app.task(name="tasks.score_customers.batch_score_all_customers", bind=True, max_retries=3)
def batch_score_all_customers(self) -> None:
    """
    Score all customers in bulk. Runs nightly via Celery Beat.
    Fetches all customers + orders from Supabase (paginated), computes RFM, bulk upserts.
    """
    try:
        logger.info("Starting nightly batch scoring for all customers...")
        
        # Paginate to fetch all database records
        customers_data = fetch_all_rows("customers", select_fields="id")
        orders_data = fetch_all_rows("orders", select_fields="*")

        df_customers = pd.DataFrame(customers_data)
        df_orders = pd.DataFrame(orders_data)

        if df_customers.empty or df_orders.empty:
            logger.info("Customers or orders table is empty. Skipping batch scoring.")
            return

        scores = compute_rfm_scores(df_customers, df_orders)

        if scores.empty:
            logger.info("No active scores computed.")
            return

        rows = scores.to_dict(orient="records")
        
        # Upsert in chunks of 500 to avoid payload size constraints on Supabase
        chunk_size = 500
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            supabase.table("customer_scores").upsert(chunk, on_conflict="customer_id").execute()

        logger.info(f"Nightly batch scoring complete. Upserted {len(rows)} customer scores.")

    except Exception as exc:
        logger.error(f"Failed nightly batch scoring: {exc}")
        raise self.retry(exc=exc, countdown=60)
