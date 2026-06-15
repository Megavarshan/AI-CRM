# Module 4 & Module 5 Report — Segment Builder, Campaign Engine & Channel Service

Both Module 4 (Segment Builder & NL2Segment) and Module 5 (Campaign Engine & Channel Service) have been fully implemented, tested, and integrated to complete the customer engagement lifecycle loop.

---

## Module 4: Segment Builder (NL2Segment)

The Segment Builder handles translating natural language customer filters (like *"customers who spent over ₹5000 but haven't bought in 60 days"*) into query specs, executing previews, and saving audience segments.

### 1. Hybrid Execution Paths (`crm/services/segment_executor.py`)
To ensure high-performance execution of queries across different database sizes:
-   **Fast Path (PostgREST Native):** For simple flat `AND` specifications, the executor leverages Supabase's native filter capabilities. This is fast, has zero overhead, and queries only the necessary indices.
-   **Complex Path (PostgREST Fallback & RPC):** For nested `AND`/`OR` logic, the executor falls back to dynamic client-side pagination matching or executes a parameterized query via a Supabase RPC function (`execute_segment_filter`).

### 2. Flagship AI Feature (`POST /segments/nl2segment`)
-   Integrates with Groq (`llama-3.3-70b-versatile` or chosen model) to convert natural language text into a structured JSON filter spec.
-   Uses lazy client initialization to prevent app startup crashes when API keys are absent.
-   Validates the AI-generated JSON against a strict schema to prevent SQL injection or execution of arbitrary fields.

---

## Module 5: Campaign Engine & Channel Webhooks

The Campaign Engine manages the creation, personalization, schedule, and execution of campaigns, interlinking CRM and the Channel Service.

### 1. Concurrency-Controlled Launching (`crm/tasks/campaigns.py`)
-   **Lazy Batch Personalization:** Personalizes messages using Groq in batches of 20 to speed up API calls while maintaining contextual consistency.
-   **Semaphored Concurrency:** Leverages an `asyncio.Semaphore` with a limit of 20 when posting to the Channel Service stub. This prevents thread pool starvation and network socket exhaustion.
-   **State Management:** Inserts communication rows in a `queued` state before calling the Channel Service, then updates them to `sent` or `failed` based on HTTP receipts.

### 2. Bidirectional Event Deduplication & Out-of-Order Safety (`crm/routers/receipts.py`)
-   **Callback Ingestion:** Receives events (`delivered`, `opened`, `clicked`, `failed`) from the Channel Service.
-   **Out-of-Order Safety:** Employs status precedence checks (`queued` < `sent` < `delivered` < `opened` < `clicked` < `failed`) to ensure that a delayed callback (e.g. `delivered`) does not regress a more advanced state (e.g. `clicked`).
-   **Atomic Counter Increments:** Increments campaign counters (`total_delivered`, `total_opened`, etc.) atomically via database-level triggers and RPCs (`increment_campaign_counter`), preventing race conditions.
-   **Finalization:** Auto-triggers campaign finalization and calls `ai_engine.generate_postmortem()` when the last communication status is resolved.

---

## Verification Plan

Both modules include comprehensive tests in `crm/tests/test_routers.py` and `crm/tests/test_campaigns.py`.
