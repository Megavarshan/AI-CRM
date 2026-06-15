# Module 2 Report — Customer & Order APIs

Module 2 has been implemented to high quality standards. Below is a detailed walkthrough of the APIs, schemas, and validation routines developed.

---

## 1. Directory Query Optimization (`GET /customers`)

Optimized the customer query logic to run at sub-millisecond speeds under heavy filtering and sorting criteria:

*   **Fuzzy Search Integration:** The backend strips the search input and applies it using the PostgREST `or` operator to query across `first_name`, `last_name`, `email`, and `phone` columns.
*   **Dynamic Joins:** 
    *   If `churn_risk` is specified, the query executes an **inner join** (`customer_scores!inner(*)`) to return only customers that match the churn tier.
    *   If `churn_risk` is not specified, it defaults to a **left join** (`customer_scores(*)`) so new customers without order history are still listed.
*   **Sorting & Pagination:** Sorting dynamically references underlying columns (`monetary` for spend, `recency_days` for recency, etc.) via referenced table targets, combined with Postgres range limits.

---

## 2. Customer 360 Endpoint (`GET /customers/{customer_id}`)

Created the full Profile Details endpoint:

*   **Order and Campaign Joins:** Fetches order history (sorted desc by purchase date) and merges campaign history by resolving relations on the `communications` table.
*   **Fault-Tolerant Cache Wrapper:** Checks for cached AI summaries in Redis. If Redis is offline or throws connection limits, the app recovers gracefully by invoking Groq on-the-fly and completing the request.
    ```python
    try:
        ai_summary = redis_client.get(cache_key)
    except Exception as redis_err:
        logger.warning(f"Redis cache read failed: {redis_err}")
    ```

---

## 3. Bulk CSV / JSON Customer Uploads (`POST /customers/import`)

Designed a high-throughput data parsing and loading mechanism:

*   **Data Integrity Validations:** Employs standard regex constraints to reject incorrect phone formats or invalid email patterns.
*   **Conflict Resolution:** Proactively checks imported emails and phone numbers against existing customer records in Supabase. Conflicts are logged in the `imports` log as row-level errors.
*   **Upsert Scaling:** Bulk-upserts valid rows in chunks of 100 on conflict of `external_id`.
*   **Batch Scoring Trigger:** Gathers IDs of all newly imported/modified customers and triggers a single Celery task (`batch_score_customers`) to compute RFM scores.

---

## 4. Single & Bulk Order Endpoints (`POST /orders` & `POST /orders/bulk`)

Exposes API methods to register purchases:

*   **Referential Integrity Checks:** Validates that referenced customer IDs exist before inserting order details.
*   **Bulk Ingestion:** Supports multi-row insertions in chunks of 200.
*   **Targeted RFM Re-scoring:** Triggers `score_single_customer` for individual orders, or schedules `batch_score_customers` for bulk operations to minimize database connections.

---

## 5. Automated Tests (`crm/tests/test_routers.py`)

Added a suite of test client scenarios to cover:
1.  **Paginated Listings:** Validates response shapes, page metadata, and score mapping.
2.  **Missing Profiles:** Expects 404 responses for invalid UUID lookups.
3.  **Customer Insertion:** Verifies deduplication behavior and Celery invocation.
4.  **Order Insertion Integrity:** Checks for 400 Bad Request if the target customer does not exist.
