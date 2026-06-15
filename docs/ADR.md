# Orbit — Architecture Decision Records

## ADR-001: Two-Service Design (CRM + Channel)

**Status:** Accepted

**Context:**
Real messaging providers (Twilio, Gupshup, etc.) are external services that accept a send request and fire back webhook callbacks asynchronously. To model this realistically, the Channel Service is a separate FastAPI process.

**Decision:**
- CRM calls `POST http://channel:8001/send` — fire and forget
- Channel service returns `202 Accepted` immediately
- Channel service uses Celery to simulate delay, then fires `POST http://crm:8000/api/v1/receipts`
- The CRM Receipt API ingests callbacks and updates communication status

**Consequences:**
- Requires two Celery workers in production
- Receipt ordering edge case: handled via idempotency keys that include status suffix

---

## ADR-002: Groq + Llama 3.3 70B for all LLM features

**Status:** Accepted

**Context:**
Need a fast, capable model that supports function/tool calling on a free tier.

**Decision:** Groq API with `llama-3.3-70b-versatile` model.
- ~200 tokens/second throughput
- Supports OpenAI-compatible function calling
- Free tier: 30 req/min

**Consequences:**
- Rate limit means large campaigns with personalization must queue Groq calls
- At scale: upgrade to paid tier or self-host via vLLM

---

## ADR-003: Supabase Realtime for live campaign stats

**Status:** Accepted

**Context:**
The campaign detail page needs to update delivery counts in real time as callbacks come in.

**Decision:**
- Use Supabase Realtime (postgres_changes) on the `campaigns` table
- Frontend subscribes per campaign_id
- No polling needed; push-based updates

**Consequences:**
- Supabase free tier: 2 simultaneous realtime channels. Sufficient for demo.
- At scale: Supabase paid tier or switch to Redis pub/sub

---

## ADR-004: RFM Scoring in pandas (not DB)

**Status:** Accepted  

**Context:**
Need churn risk scores for all customers, always fresh.

**Decision:** pandas in-memory computation via Celery tasks.
- Works up to ~1M customers
- Nightly batch job + per-order trigger for single customer re-scoring

**Consequences:**
- At scale (>1M): push computation to PostgreSQL window functions or dbt
