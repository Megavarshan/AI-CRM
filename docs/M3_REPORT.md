# Module 3 Report — RFM Scoring Engine

Module 3 has been fully optimized to meet production scale limits. Below is a summary of the improvements and fixes implemented.

---

## 1. Fail-Safe Quantile Binning (`safe_qcut`)

The standard pandas `pd.qcut` operation divides values into equal-sized buckets. However, it crashes with a `ValueError` in two production scenarios:
1.  **Small Datasets:** When the database contains fewer customers than bins (e.g. fewer than 5 customers), dividing them into 5 bins is mathematically impossible.
2.  **Duplicate Edges (Skewed Data):** When many customers share identical metrics (e.g. all having a frequency of 1, or recency of 0), quantile thresholds overlap, leading to collapsed bins.

*   **Solution:** We replaced raw `pd.qcut` calls with a custom `safe_qcut` helper.
*   **Rank-Based Unique Edges:** It uses `.rank(method="first")` to assign unique rankings to identical raw metrics, guaranteeing bin uniqueness.
*   **Linear Scaling Fallback:** For small datasets, it falls back to linear rank scaling across the bin labels (`1..5`), avoiding binning exceptions completely.

---

## 2. Scalable Supabase Pagination (`fetch_all_rows`)

Supabase / PostgREST queries enforce a max return size (typically 1000 rows) to protect server performance. Simply querying `.select("*")` on large tables returns partial history, leading to highly inaccurate RFM scores.

*   **Solution:** Implemented `fetch_all_rows` in `tasks/score_customers.py`.
*   **Dynamic Range Crawling:** Crawls tables using successive `.range(offset, offset + chunk_size - 1)` requests until all database rows are pulled.
*   **Chunked Upserts:** Nightly upserts of scores back to Supabase are now chunked (500 records per request) to prevent HTTP payload ceiling issues.

---

## 3. High-Performance Celery Tasks (`crm/tasks/score_customers.py`)

*   **`score_single_customer`:** Triggered immediately when a single customer is created or order is processed. Computes metrics instantly.
*   **`batch_score_customers`:** Receives a list of customer IDs (e.g. from an import event). It chunk-queries only the relevant orders in batches of 200 and performs a bulk upsert, avoiding unnecessary full-table sweeps.
*   **`batch_score_all_customers` (Celery Beat):** Nightly re-scoring job. Uses the new pagination and chunking helpers to process the entire database securely.

---

## 4. Automated Tests (`crm/tests/test_rfm_scorer.py`)

*   Added `test_rfm_scorer_small_dataset()` to ensure that the scoring engine operates smoothly without exceptions when given just 2 customers.
