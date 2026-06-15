# Orbit — AI-Native Mini CRM

> **"Your brand. Your shoppers. One AI that connects them."**

Orbit is a full-stack, AI-native mini CRM built for Direct-to-Consumer and retail brands. It helps marketers decide **who to talk to**, **what to say**, and **how well it worked** — powered by open-source LLMs (Groq + Llama 3.3 70B), agentic tool calling, and a fully simulated two-service messaging loop.

Built as a submission for the Xeno Engineering Take-Home Assignment (June 2026).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Repository Structure](#4-repository-structure)
5. [Data Models](#5-data-models)
6. [Backend — CRM Service](#6-backend--crm-service)
7. [Backend — Channel Service (Stub)](#7-backend--channel-service-stub)
8. [AI Engine](#8-ai-engine)
9. [Frontend — All Screens](#9-frontend--all-screens)
10. [Onboarding — How a Startup Uses Orbit](#10-onboarding--how-a-startup-uses-orbit)
11. [Seed Data](#11-seed-data)
12. [Environment Variables](#12-environment-variables)
13. [Running Locally](#13-running-locally)
14. [Deployment](#14-deployment)
15. [Scale Assumptions & Tradeoffs](#15-scale-assumptions--tradeoffs)

---

## 1. Project Overview

### What Orbit Does

A marketer at a fashion label, coffee chain, or beauty brand logs into Orbit. They see:

- Which customers are about to churn (churn risk scored via RFM model)
- Segment builder — type in natural language or use filters
- Campaign wizard — pick segment, channel, let AI write personalized messages
- Live delivery tracking — watch messages go from `sent → delivered → opened → clicked`
- AI Copilot — one chat interface that plans and executes entire campaigns autonomously
- Post-campaign AI analyst — written post-mortem after every campaign

### What Makes It "AI-Native"

AI is not bolted on. It is the product:

- **NL2Segment**: Natural language → structured DB query → live segment count
- **Per-customer personalization**: Every recipient gets a unique, context-rich message (Zomato-style)
- **Agentic campaign execution**: LLM calls real tool functions autonomously with visible reasoning trace
- **Churn risk scoring**: RFM model runs on every customer, always up to date
- **Post-campaign analyst**: LLM writes a post-mortem with concrete recommendations after each campaign

---

## 2. Architecture

```
┌─────────────────────┐         ┌──────────────────────────────────────────┐
│   Next.js Frontend  │──REST──▶│           CRM Backend (FastAPI)           │
│   React + shadcn    │◀──JSON──│                                          │
└─────────────────────┘         │  ┌──────────────┐  ┌──────────────────┐ │
                                 │  │  REST API    │  │    AI Engine     │ │
                                 │  │  layer       │  │  Groq + Llama    │ │
                                 │  └──────────────┘  └──────────────────┘ │
                                 │  ┌──────────────┐  ┌──────────────────┐ │
                                 │  │  RFM Scorer  │  │  Celery Workers  │ │
                                 │  │  (pandas)    │  │  (async jobs)    │ │
                                 │  └──────────────┘  └──────────────────┘ │
                                 │  ┌──────────────┐                       │
                                 │  │  Receipt API │ ◀─── callbacks ───┐   │
                                 │  └──────────────┘                   │   │
                                 │  ┌──────────────────────────────┐   │   │
                                 │  │   Supabase (PostgreSQL)      │   │   │
                                 │  └──────────────────────────────┘   │   │
                                 └─────────────────────────────────────┼───┘
                                          POST /send ──────────────────▼
                                 ┌─────────────────────────────────────────┐
                                 │        Channel Service (FastAPI stub)    │
                                 │  • Accepts send requests                 │
                                 │  • Simulates delay (1–10s via Celery)    │
                                 │  • Probabilistic lifecycle simulation    │
                                 │  • Fires POST /receipts back to CRM      │
                                 └─────────────────────────────────────────┘

Redis ──── Celery task queue (shared by both services)
Groq  ──── External LLM API (free tier, Llama 3.3 70B)
```

### Two-Service Design (Critical)

The CRM and Channel Service are **two separate FastAPI processes**. They communicate over HTTP only:

- CRM calls `POST http://channel-service/send` with the message payload
- Channel service returns `202 Accepted` immediately (async)
- Channel service uses Celery to simulate delay, then fires `POST http://crm/api/v1/receipts` with delivery status
- CRM Receipt API ingests the callback and updates the communication record in the DB

This models how real messaging providers (Twilio, Gupshup, etc.) actually work — webhook callbacks, not synchronous responses.

---

## 3. Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| CRM Backend | Python 3.11 + FastAPI | AI libraries (Groq SDK, pandas) are Python-native |
| Channel Service | Python 3.11 + FastAPI | Separate process, same language |
| Task Queue | Celery 5 + Redis | Async jobs, retry logic, models real webhook pattern |
| Database | Supabase (PostgreSQL 15) | Postgres + realtime subscriptions + auth + free hosted tier |
| LLM Provider | Groq API (Llama 3.3 70B) | Free tier, ~200 tokens/s, supports function/tool calling |
| RFM Scoring | pandas + numpy | Lightweight, no external ML service needed |
| Frontend | Next.js 14 (App Router) | SSR, fast routing, React Server Components |
| UI Components | shadcn/ui + Tailwind CSS | Enterprise-looking, accessible, fast to build with |
| Realtime UI | Supabase Realtime (websocket) | Push campaign stat updates to frontend without polling |
| Hosting — CRM | Render (free tier) | Easy FastAPI deploy, persistent workers |
| Hosting — Channel | Render (separate service) | Deploy as a second web service on same Render account |
| Hosting — Frontend | Vercel (free tier) | Native Next.js hosting |
| Hosting — Redis | Render Redis (free tier) | Shared between both services |

---

## 4. Repository Structure

```
orbit/
├── crm/                          # CRM Backend service
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Settings (env vars, Supabase client)
│   ├── celery_app.py             # Celery instance + Redis config
│   ├── models/
│   │   ├── customer.py           # Pydantic models for customers
│   │   ├── order.py              # Pydantic models for orders
│   │   ├── segment.py            # Pydantic models for segments
│   │   ├── campaign.py           # Pydantic models for campaigns
│   │   └── communication.py     # Pydantic models for individual messages
│   ├── routers/
│   │   ├── customers.py          # GET/POST /customers endpoints
│   │   ├── orders.py             # GET/POST /orders endpoints
│   │   ├── segments.py           # GET/POST /segments + NL2Segment
│   │   ├── campaigns.py          # GET/POST /campaigns + launch
│   │   ├── receipts.py           # POST /receipts (channel callbacks)
│   │   ├── analytics.py          # GET /analytics endpoints
│   │   └── copilot.py            # POST /copilot/chat (agent endpoint)
│   ├── services/
│   │   ├── rfm_scorer.py         # RFM scoring logic with pandas
│   │   ├── segment_executor.py   # Translates filter specs → SQL queries
│   │   ├── campaign_sender.py    # Calls channel service POST /send
│   │   └── ai_engine.py          # All LLM calls (NL2Segment, personalize, agent)
│   ├── tasks/
│   │   └── score_customers.py    # Celery task: batch RFM scoring
│   ├── db/
│   │   ├── schema.sql            # Full Supabase schema (run once)
│   │   └── seed.py               # Seed script: fake customers + orders
│   └── requirements.txt
│
├── channel/                      # Channel Service (stub)
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Settings
│   ├── celery_app.py             # Celery instance (same Redis)
│   ├── routers/
│   │   └── send.py               # POST /send endpoint
│   ├── tasks/
│   │   └── simulate_delivery.py  # Celery task: simulate lifecycle + fire callbacks
│   └── requirements.txt
│
├── frontend/                     # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # Redirects to /dashboard
│   │   ├── dashboard/page.tsx
│   │   ├── customers/
│   │   │   ├── page.tsx          # Customer list
│   │   │   └── [id]/page.tsx     # Customer detail
│   │   ├── segments/page.tsx
│   │   ├── campaigns/
│   │   │   ├── page.tsx          # Campaign list
│   │   │   └── [id]/page.tsx     # Live campaign stats
│   │   ├── copilot/page.tsx      # AI Copilot chat
│   │   └── analytics/page.tsx
│   ├── components/
│   │   ├── ui/                   # shadcn/ui components (button, card, etc.)
│   │   ├── CustomerTable.tsx
│   │   ├── SegmentBuilder.tsx
│   │   ├── NLSegmentBox.tsx
│   │   ├── CampaignWizard.tsx
│   │   ├── CopilotChat.tsx
│   │   ├── ToolCallTrace.tsx     # Shows agent tool calls visually
│   │   ├── DeliveryTracker.tsx   # Realtime campaign stats
│   │   ├── ChurnBadge.tsx
│   │   └── MessagePreview.tsx
│   ├── lib/
│   │   ├── api.ts                # Typed API client (fetch wrappers)
│   │   └── supabase.ts           # Supabase realtime client
│   └── package.json
│
├── docker-compose.yml            # Local dev: crm + channel + redis
└── README.md
```

---

## 5. Data Models

### Supabase Schema (`crm/db/schema.sql`)

#### `customers` table

```sql
CREATE TABLE customers (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id     TEXT UNIQUE,           -- brand's own customer ID (for dedup on import)
  first_name      TEXT NOT NULL,
  last_name       TEXT,
  phone           TEXT UNIQUE,           -- E.164 format e.g. +919876543210
  email           TEXT UNIQUE,
  city            TEXT,
  channel_pref    TEXT DEFAULT 'whatsapp' CHECK (channel_pref IN ('whatsapp','sms','email','rcs')),
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### `orders` table

```sql
CREATE TABLE orders (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id     UUID REFERENCES customers(id) ON DELETE CASCADE,
  order_date      TIMESTAMPTZ NOT NULL,
  amount          NUMERIC(10,2) NOT NULL,   -- in INR
  category        TEXT,                     -- e.g. "skincare", "apparel", "coffee"
  product_name    TEXT,                     -- most recent / primary product in order
  status          TEXT DEFAULT 'completed' CHECK (status IN ('completed','returned','cancelled')),
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### `customer_scores` table

```sql
CREATE TABLE customer_scores (
  customer_id     UUID PRIMARY KEY REFERENCES customers(id) ON DELETE CASCADE,
  recency_days    INTEGER,               -- days since last completed order
  frequency       INTEGER,               -- total completed orders
  monetary        NUMERIC(10,2),         -- total spend
  rfm_score       NUMERIC(5,2),          -- composite 0–100
  churn_risk      TEXT CHECK (churn_risk IN ('low','medium','high','critical')),
  top_category    TEXT,                  -- most purchased category
  last_product    TEXT,                  -- product name from most recent order
  scored_at       TIMESTAMPTZ DEFAULT NOW()
);
```

#### `segments` table

```sql
CREATE TABLE segments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  description     TEXT,
  filter_spec     JSONB NOT NULL,        -- structured filter (see Section 8)
  nl_query        TEXT,                  -- original natural language input if any
  customer_count  INTEGER DEFAULT 0,    -- cached count, refreshed on demand
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### `campaigns` table

```sql
CREATE TABLE campaigns (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  segment_id      UUID REFERENCES segments(id),
  channel         TEXT NOT NULL CHECK (channel IN ('whatsapp','sms','email','rcs')),
  message_template TEXT NOT NULL,        -- base template (may contain {first_name} etc.)
  personalized    BOOLEAN DEFAULT TRUE,  -- if true, AI generates per-customer messages
  status          TEXT DEFAULT 'draft' CHECK (status IN ('draft','scheduled','running','completed','failed')),
  scheduled_at    TIMESTAMPTZ,
  launched_at     TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  created_by      TEXT DEFAULT 'marketer',  -- 'marketer' or 'copilot' (agent-created)
  total_sent      INTEGER DEFAULT 0,
  total_delivered INTEGER DEFAULT 0,
  total_opened    INTEGER DEFAULT 0,
  total_clicked   INTEGER DEFAULT 0,
  total_failed    INTEGER DEFAULT 0,
  ai_postmortem   TEXT,                  -- LLM-generated post-campaign analysis
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### `communications` table

```sql
CREATE TABLE communications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id     UUID REFERENCES campaigns(id) ON DELETE CASCADE,
  customer_id     UUID REFERENCES customers(id) ON DELETE CASCADE,
  channel         TEXT NOT NULL,
  personalized_message TEXT NOT NULL,    -- the actual message sent to this customer
  status          TEXT DEFAULT 'queued' CHECK (
                    status IN ('queued','sent','delivered','failed','opened','clicked')
                  ),
  idempotency_key TEXT UNIQUE,           -- prevents double-counting callbacks
  sent_at         TIMESTAMPTZ,
  delivered_at    TIMESTAMPTZ,
  opened_at       TIMESTAMPTZ,
  clicked_at      TIMESTAMPTZ,
  failed_at       TIMESTAMPTZ,
  failure_reason  TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### `imports` table

```sql
CREATE TABLE imports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename        TEXT,
  rows_total      INTEGER,
  rows_imported   INTEGER,
  rows_failed     INTEGER,
  status          TEXT DEFAULT 'processing' CHECK (status IN ('processing','completed','failed')),
  error_log       JSONB,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Backend — CRM Service

### `GET /api/v1/customers`

Returns paginated customer list with scores joined.

**Query params:**
- `page` (int, default 1)
- `limit` (int, default 50, max 200)
- `search` (string) — fuzzy match on name, phone, email
- `churn_risk` (string) — filter by `low | medium | high | critical`
- `sort_by` (string) — `spend | recency | orders | churn_risk`
- `sort_dir` (string) — `asc | desc`

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "first_name": "Priya",
      "last_name": "Sharma",
      "phone": "+919876543210",
      "email": "priya@example.com",
      "city": "Mumbai",
      "channel_pref": "whatsapp",
      "score": {
        "recency_days": 45,
        "frequency": 7,
        "monetary": 8400.00,
        "rfm_score": 72.5,
        "churn_risk": "high",
        "top_category": "skincare",
        "last_product": "Rose Serum 50ml"
      }
    }
  ],
  "total": 1247,
  "page": 1,
  "limit": 50
}
```

### `GET /api/v1/customers/{id}`

Returns full customer profile including:
- All orders (paginated, sorted by date desc)
- Current churn score
- All campaigns this customer was part of
- AI-generated 360 summary (generated on demand, cached for 1 hour in Redis)

**AI 360 Summary generation prompt** (in `ai_engine.py`):
```python
def generate_customer_summary(customer: dict, orders: list, campaigns: list) -> str:
    prompt = f"""
    You are a CRM analyst. Write a 2-sentence customer summary for a marketer.
    Include: purchase pattern, top category, churn risk reason, and ONE suggested action.
    Keep it under 60 words. Be specific, not generic.

    Customer: {customer['first_name']} {customer['last_name']}, {customer['city']}
    Orders: {len(orders)} total, last order {customer['score']['recency_days']} days ago
    Top category: {customer['score']['top_category']}
    Last product: {customer['score']['last_product']}
    Total spend: ₹{customer['score']['monetary']}
    Churn risk: {customer['score']['churn_risk']}
    Recent campaigns: {[c['name'] for c in campaigns[-3:]]}
    """
```

### `POST /api/v1/customers`

Create a single customer.

**Body:**
```json
{
  "first_name": "Rahul",
  "last_name": "Mehta",
  "phone": "+919123456789",
  "email": "rahul@example.com",
  "city": "Bangalore",
  "channel_pref": "whatsapp",
  "external_id": "CUST_001"
}
```

Triggers Celery task `score_single_customer` after insert.

### `POST /api/v1/customers/import`

Accepts multipart file upload (CSV or JSON).

**CSV format expected:**
```
external_id,first_name,last_name,phone,email,city,channel_pref
CUST_001,Priya,Sharma,+919876543210,priya@example.com,Mumbai,whatsapp
```

**Process:**
1. Parse with pandas
2. Validate: phone format (E.164), required fields, dedup on `external_id` or `phone`
3. Batch insert into `customers` (upsert on `external_id`)
4. Create an `imports` record, return `import_id`
5. Trigger Celery task `batch_score_customers` for all newly inserted customers

**Response:**
```json
{
  "import_id": "uuid",
  "rows_total": 500,
  "rows_imported": 498,
  "rows_failed": 2,
  "status": "completed",
  "errors": [
    {"row": 43, "reason": "invalid phone format"},
    {"row": 201, "reason": "duplicate email"}
  ]
}
```

### `POST /api/v1/orders`

Create a single order. Also accepts `POST /api/v1/orders/bulk` for array of orders.

**Body:**
```json
{
  "customer_id": "uuid",
  "order_date": "2025-11-12T14:30:00Z",
  "amount": 1299.00,
  "category": "skincare",
  "product_name": "Rose Serum 50ml",
  "status": "completed"
}
```

After insert, triggers `score_single_customer` Celery task to refresh RFM for that customer.

### `GET /api/v1/segments`

Returns all segments with `customer_count`, `filter_spec`, and `nl_query`.

### `POST /api/v1/segments`

Create a segment from a structured filter spec (direct from filter builder UI).

**Body:**
```json
{
  "name": "High-value lapsed",
  "description": "Spent over 5000, no order in 60 days",
  "filter_spec": {
    "operator": "AND",
    "conditions": [
      { "field": "monetary", "op": "gte", "value": 5000 },
      { "field": "recency_days", "op": "gte", "value": 60 }
    ]
  }
}
```

### `POST /api/v1/segments/nl2segment`

**The flagship AI feature.** Takes a natural language query, translates it to a `filter_spec`, executes it, and returns the count + preview customers.

**Body:**
```json
{
  "query": "customers who spent over 5000 rupees but haven't bought anything in the last 60 days"
}
```

**Process:**
1. Send query to Groq with structured output prompt (see AI Engine section)
2. LLM returns a `filter_spec` JSON
3. `segment_executor.py` translates `filter_spec` → parameterized SQL
4. Execute against Supabase, get count + first 5 customer names
5. Return all three: `filter_spec`, `count`, `preview`

**Response:**
```json
{
  "filter_spec": {
    "operator": "AND",
    "conditions": [
      { "field": "monetary", "op": "gte", "value": 5000 },
      { "field": "recency_days", "op": "gte", "value": 60 }
    ]
  },
  "customer_count": 847,
  "preview": ["Priya Sharma", "Rahul Mehta", "Aisha Khan", "Vikram Patel", "Neha Joshi"],
  "nl_query": "customers who spent over 5000 rupees but haven't bought anything in the last 60 days"
}
```

### `POST /api/v1/segments/{id}/refresh`

Re-execute the segment's `filter_spec` against current data and update `customer_count`.

### `GET /api/v1/campaigns`

Returns all campaigns with stats.

**Query params:** `status`, `page`, `limit`

### `POST /api/v1/campaigns`

Create a campaign in `draft` status.

**Body:**
```json
{
  "name": "Diwali Re-engagement",
  "segment_id": "uuid",
  "channel": "whatsapp",
  "message_template": "Hey {first_name}, we miss you! Come back for our Diwali sale.",
  "personalized": true,
  "scheduled_at": null
}
```

### `POST /api/v1/campaigns/{id}/launch`

Launches the campaign. This is the most complex endpoint.

**Process:**
1. Fetch all customers in the segment (paginated, 100 at a time)
2. If `personalized=true`: call Groq in batches of 20 to generate personalized messages (see AI Engine)
3. Insert one `communications` record per customer with status `queued`
4. For each communication, call `POST http://channel-service/send` with payload
5. Update communication status to `sent`
6. Update `campaigns.status` to `running`, set `launched_at`
7. Update `campaigns.total_sent`

**Payload sent to channel service per message:**
```json
{
  "communication_id": "uuid",
  "campaign_id": "uuid",
  "customer_id": "uuid",
  "channel": "whatsapp",
  "recipient_phone": "+919876543210",
  "recipient_email": null,
  "message": "Hey Priya, your Rose Serum is almost done, isn't it? 😊 Grab a refill — 15% off just for you.",
  "idempotency_key": "comm_uuid_attempt_1"
}
```

### `GET /api/v1/campaigns/{id}/stats`

Returns live campaign stats.

**Response:**
```json
{
  "campaign_id": "uuid",
  "name": "Diwali Re-engagement",
  "status": "running",
  "total_sent": 847,
  "total_delivered": 812,
  "total_opened": 543,
  "total_clicked": 201,
  "total_failed": 35,
  "delivery_rate": 95.9,
  "open_rate": 66.9,
  "click_rate": 37.1,
  "channel_breakdown": {
    "whatsapp": { "sent": 847, "delivered": 812, "opened": 543 }
  },
  "ai_postmortem": null
}
```

### `POST /api/v1/receipts`

**Receipt callback endpoint.** Called by the channel service. This is the other half of the two-service loop.

**Body:**
```json
{
  "communication_id": "uuid",
  "campaign_id": "uuid",
  "idempotency_key": "comm_uuid_attempt_1",
  "status": "delivered",
  "timestamp": "2026-06-12T10:23:45Z"
}
```

**Process:**
1. Check `idempotency_key` — if already processed, return `200 OK` silently (dedup)
2. Update `communications` record: set `status` and the relevant `*_at` timestamp
3. Increment the corresponding counter on `campaigns` (atomic `UPDATE campaigns SET total_delivered = total_delivered + 1`)
4. If this receipt pushes `total_delivered + total_failed = total_sent` → all messages resolved → trigger `finalize_campaign` Celery task
5. Broadcast update via Supabase Realtime so frontend updates live

**`finalize_campaign` Celery task:**
- Sets `campaigns.status = 'completed'`, sets `completed_at`
- Calls `ai_engine.generate_postmortem(campaign_id)` → stores result in `campaigns.ai_postmortem`

### `GET /api/v1/analytics/overview`

**Response:**
```json
{
  "total_customers": 1247,
  "customers_at_risk": 312,
  "active_campaigns": 3,
  "revenue_influenced_30d": 124500.00,
  "messages_delivered_30d": 8432,
  "avg_open_rate_30d": 61.4
}
```

### `GET /api/v1/analytics/campaigns`

Returns per-campaign performance for the last 90 days, sorted by `open_rate` desc.

### `GET /api/v1/analytics/channels`

Channel-by-channel comparison: WhatsApp vs SMS vs Email open/click rates.

### `POST /api/v1/copilot/chat`

The agentic AI Copilot endpoint. Handles multi-turn conversation with tool calling.

**Body:**
```json
{
  "messages": [
    { "role": "user", "content": "I want to re-engage customers who bought from us last Diwali but went quiet" }
  ],
  "session_id": "uuid"
}
```

See full agent spec in Section 8 (AI Engine).

---

## 7. Backend — Channel Service (Stub)

A completely separate FastAPI process. Its job is to receive send requests, simulate realistic delivery lifecycle, and fire callbacks to the CRM.

### `POST /send`

**Body:** (same payload CRM sends, documented above)

**Response:** `202 Accepted` immediately, always.

```json
{ "accepted": true, "communication_id": "uuid" }
```

After returning 202, enqueues a Celery task `simulate_delivery`.

### Celery Task: `simulate_delivery`

**In `channel/tasks/simulate_delivery.py`:**

```python
import random
import time
from celery import chain
from channel.celery_app import app
import httpx

# Channel-specific open and click rate weights
CHANNEL_RATES = {
    "whatsapp": {"deliver": 0.97, "open": 0.72, "click": 0.38},
    "sms":      {"deliver": 0.94, "open": 0.45, "click": 0.12},
    "email":    {"deliver": 0.91, "open": 0.28, "click": 0.08},
    "rcs":      {"deliver": 0.95, "open": 0.60, "click": 0.30},
}

FAILURE_RATE = 0.05  # 5% of messages fail

@app.task(bind=True, max_retries=3, default_retry_delay=30)
def simulate_delivery(self, payload: dict):
    channel = payload["channel"]
    rates = CHANNEL_RATES.get(channel, CHANNEL_RATES["whatsapp"])
    comm_id = payload["communication_id"]
    idempotency_key = payload["idempotency_key"]
    crm_receipt_url = settings.CRM_RECEIPT_URL  # e.g. http://crm:8000/api/v1/receipts

    def fire_callback(status: str, delay_s: float):
        time.sleep(delay_s)
        try:
            httpx.post(crm_receipt_url, json={
                "communication_id": comm_id,
                "campaign_id": payload["campaign_id"],
                "idempotency_key": f"{idempotency_key}_{status}",
                "status": status,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, timeout=10)
        except Exception as exc:
            # Retry the task on network failure
            raise self.retry(exc=exc)

    # Step 1: Random initial delay (1–8 seconds simulates network latency)
    initial_delay = random.uniform(1, 8)

    # Step 2: Determine if this message fails outright
    if random.random() < FAILURE_RATE:
        fire_callback("failed", initial_delay)
        return

    # Step 3: Delivered
    fire_callback("delivered", initial_delay)

    # Step 4: Opened (probabilistic, only if delivered)
    if random.random() < rates["open"]:
        fire_callback("opened", initial_delay + random.uniform(2, 30))

        # Step 5: Clicked (only if opened)
        if random.random() < rates["click"]:
            fire_callback("clicked", initial_delay + random.uniform(30, 120))
```

**Key design decisions:**
- Returns `202` immediately — never blocks the CRM
- Each status fires a **separate callback** (not one combined payload) — mirrors real provider behavior where each event arrives independently
- `idempotency_key` includes the status suffix (`_delivered`, `_opened`) so CRM can dedup each event type independently
- 5% failure rate with Celery retry on network errors
- Channel-weighted rates: WhatsApp has highest open rates, Email lowest

---

## 8. AI Engine

All LLM logic lives in `crm/services/ai_engine.py`. Uses Groq client (drop-in compatible with OpenAI SDK).

### Setup

```python
from groq import Groq

client = Groq(api_key=settings.GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile"   # best for tool use on Groq free tier
```

### Feature 1: NL2Segment

Translates natural language to a structured `filter_spec` JSON.

**Supported filter fields:**
```
monetary          → total spend (float, INR)
recency_days      → days since last order (int)
frequency         → total completed orders (int)
churn_risk        → 'low' | 'medium' | 'high' | 'critical'
top_category      → string (e.g. 'skincare', 'apparel')
city              → string
channel_pref      → 'whatsapp' | 'sms' | 'email' | 'rcs'
rfm_score         → composite score 0–100 (float)
```

**Supported operators:** `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`

**Supported combinators:** `AND`, `OR`

```python
NL2SEGMENT_SYSTEM_PROMPT = """
You are a CRM query translator. Convert natural language customer segment descriptions into a structured JSON filter spec.

The filter spec format is:
{
  "operator": "AND" | "OR",
  "conditions": [
    { "field": "<field_name>", "op": "<operator>", "value": <value> }
  ]
}

Available fields: monetary (float, INR), recency_days (int), frequency (int),
churn_risk ('low'|'medium'|'high'|'critical'), top_category (string),
city (string), channel_pref (string), rfm_score (float 0-100)

Available operators: eq, neq, gt, gte, lt, lte, in, not_in, contains

Rules:
- "haven't bought in X days" → recency_days gte X
- "spent over ₹X" or "high value" → monetary gte X
- "loyal customers" → frequency gte 5
- "at risk" or "churning" → churn_risk in ['high','critical']
- Nested AND/OR is allowed using a 'conditions' array with its own 'operator'
- Return ONLY valid JSON. No explanation. No markdown. No preamble.
"""

def nl_to_segment(query: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": NL2SEGMENT_SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ],
        temperature=0,
        max_tokens=500
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)   # parse the JSON filter spec
```

**`segment_executor.py`** then translates the `filter_spec` to SQL:

```python
def filter_spec_to_sql(spec: dict) -> tuple[str, list]:
    """
    Converts a filter_spec dict into a parameterized WHERE clause.
    Returns (where_clause_string, params_list)
    
    Base query joins customers + customer_scores:
    SELECT c.*, s.* FROM customers c
    JOIN customer_scores s ON s.customer_id = c.id
    WHERE <generated clause>
    """
    FIELD_MAP = {
        "monetary": "s.monetary",
        "recency_days": "s.recency_days",
        "frequency": "s.frequency",
        "churn_risk": "s.churn_risk",
        "top_category": "s.top_category",
        "city": "c.city",
        "channel_pref": "c.channel_pref",
        "rfm_score": "s.rfm_score",
    }
    OP_MAP = {
        "eq": "=", "neq": "!=", "gt": ">", "gte": ">=",
        "lt": "<", "lte": "<=", "contains": "ILIKE"
    }
    # Recursively build clause from nested AND/OR conditions
    ...
```

### Feature 2: Per-Customer Message Personalization

Generates unique Zomato-style messages per customer in batches.

```python
PERSONALIZATION_SYSTEM_PROMPT = """
You are a CRM message writer for a D2C brand. Generate personalized WhatsApp/SMS messages.

Rules:
- Always use the customer's first name
- Reference their specific last product or top category
- Mention time since last order if it adds context
- Create gentle urgency without being pushy
- Warm, conversational tone — like a helpful friend, not a brand announcement
- Under 160 characters for SMS, under 300 for WhatsApp
- Maximum 1 emoji, at end of sentence only
- No hashtags. No "Dear Customer". No corporate speak.

Good examples:
- "Hey Priya, your Rose Serum is almost done, isn't it? 😊 Grab a refill today — 15% off just for you."
- "Rahul, your last order was 3 weeks ago. Your cart misses you. Here's ₹100 to come back."
- "Aisha! Your favourite Mango Tango blend is back in stock. Order in the next 2 hours, get free delivery."
- "Vikram, it's been 45 days since your last skincare order. Your skin noticed. 😄 Come back?"

Return ONLY a JSON array of message strings, one per customer, in the same order as the input.
No explanation. No markdown.
"""

def generate_personalized_messages(customers: list[dict], campaign_brief: str, channel: str) -> list[str]:
    """
    customers: list of dicts with first_name, last_product, top_category,
               recency_days, city, channel_pref
    Returns: list of personalized message strings, same length as customers
    """
    batch_size = 20  # process 20 customers per LLM call

    customer_contexts = []
    for c in customers:
        customer_contexts.append({
            "name": c["first_name"],
            "last_product": c.get("last_product", c.get("top_category", "your last order")),
            "days_ago": c["recency_days"],
            "top_category": c.get("top_category", ""),
            "city": c.get("city", "")
        })

    user_prompt = f"""
Campaign goal: {campaign_brief}
Channel: {channel}

Generate one personalized message per customer:
{json.dumps(customer_contexts, indent=2)}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PERSONALIZATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    messages = json.loads(response.choices[0].message.content.strip())
    return messages
```

### Feature 3: Agentic Copilot (Tool Calling)

The AI Copilot endpoint uses Groq's function calling to let the LLM autonomously plan and execute campaigns.

**Tools available to the agent:**

```python
COPILOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_segments",
            "description": "List all saved segments with customer counts. Use to find an appropriate audience.",
            "parameters": {
                "type": "object",
                "properties": {
                    "churn_risk_filter": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical", "any"],
                        "description": "Filter segments by churn risk level"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_segment_from_nl",
            "description": "Create a new customer segment from a natural language description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "nl_query": {"type": "string", "description": "Natural language description of the segment"}
                },
                "required": ["name", "nl_query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draft_message",
            "description": "Draft a campaign message template for a given goal and channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_goal": {"type": "string"},
                    "channel": {"type": "string", "enum": ["whatsapp", "sms", "email", "rcs"]},
                    "tone": {"type": "string", "enum": ["warm", "urgent", "celebratory", "informational"]}
                },
                "required": ["campaign_goal", "channel"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_campaign",
            "description": "Create a campaign with a segment, channel, and message template.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "segment_id": {"type": "string"},
                    "channel": {"type": "string"},
                    "message_template": {"type": "string"},
                    "personalized": {"type": "boolean", "default": True}
                },
                "required": ["name", "segment_id", "channel", "message_template"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_campaign",
            "description": "Launch a campaign. Ask for user confirmation before calling this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "confirm": {"type": "boolean", "description": "Must be true — user must confirm before launch"}
                },
                "required": ["campaign_id", "confirm"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_stats",
            "description": "Get live delivery stats for a running or completed campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"}
                },
                "required": ["campaign_id"]
            }
        }
    }
]
```

**Agent loop in `routers/copilot.py`:**

```python
async def copilot_chat(messages: list[dict]) -> AsyncGenerator:
    """
    Runs the agentic loop. Yields events to the frontend as Server-Sent Events (SSE).
    Each event has a type: 'text' | 'tool_call' | 'tool_result' | 'done'
    """
    system = """
    You are Orbit Copilot, an AI campaign manager for a D2C brand.
    Your job is to help marketers plan and execute re-engagement campaigns.
    
    Workflow:
    1. Understand the marketer's goal
    2. Use get_segments to find or create an appropriate audience
    3. Use draft_message to write the message
    4. Use create_campaign to set it up
    5. ALWAYS ask for explicit confirmation before calling launch_campaign
    6. After launch, use get_campaign_stats to report progress
    
    Be concise. Show your reasoning. Ask for confirmation at key steps.
    When calling tools, explain what you're doing and why.
    """

    conversation = [{"role": "system", "content": system}] + messages

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=conversation,
            tools=COPILOT_TOOLS,
            tool_choice="auto",
            max_tokens=1000,
            stream=False
        )

        message = response.choices[0].message

        # Stream the text back to frontend
        if message.content:
            yield {"type": "text", "content": message.content}

        # If no tool calls, we're done
        if not message.tool_calls:
            yield {"type": "done"}
            break

        # Execute each tool call
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            # Stream the tool call to frontend (so user sees the reasoning trace)
            yield {"type": "tool_call", "name": tool_name, "args": tool_args}

            # Execute the actual tool
            result = await execute_tool(tool_name, tool_args)

            # Stream the result
            yield {"type": "tool_result", "name": tool_name, "result": result}

            # Add to conversation for next loop iteration
            conversation.append(message)
            conversation.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })
```

**Frontend renders each SSE event type differently:**
- `tool_call` → shows a "calling `tool_name`..." step card with the args
- `tool_result` → shows the result beneath the step card
- `text` → renders as the assistant's chat bubble
- `done` → stops the spinner

### Feature 4: RFM Scoring (`services/rfm_scorer.py`)

```python
def compute_rfm_scores(df_customers: pd.DataFrame, df_orders: pd.DataFrame) -> pd.DataFrame:
    """
    df_customers: customers table
    df_orders: orders table (completed orders only)
    
    Returns DataFrame with columns:
    customer_id, recency_days, frequency, monetary, rfm_score, churn_risk,
    top_category, last_product
    """
    today = pd.Timestamp.utcnow()

    # Aggregate orders per customer
    agg = df_orders[df_orders['status'] == 'completed'].groupby('customer_id').agg(
        last_order_date=('order_date', 'max'),
        frequency=('id', 'count'),
        monetary=('amount', 'sum'),
        top_category=('category', lambda x: x.value_counts().index[0] if len(x) > 0 else None),
        last_product=('product_name', 'last')
    ).reset_index()

    agg['recency_days'] = (today - pd.to_datetime(agg['last_order_date'])).dt.days

    # Score each dimension 1–5 using quintiles
    agg['r_score'] = pd.qcut(agg['recency_days'], 5, labels=[5,4,3,2,1])    # lower recency = better
    agg['f_score'] = pd.qcut(agg['frequency'].rank(method='first'), 5, labels=[1,2,3,4,5])
    agg['m_score'] = pd.qcut(agg['monetary'].rank(method='first'), 5, labels=[1,2,3,4,5])

    # Composite score (weighted: recency 40%, frequency 30%, monetary 30%)
    agg['rfm_score'] = (
        agg['r_score'].astype(float) * 0.4 +
        agg['f_score'].astype(float) * 0.3 +
        agg['m_score'].astype(float) * 0.3
    ) * 20  # normalize to 0–100

    # Churn risk buckets
    def churn_bucket(row):
        if row['recency_days'] > 90 or row['rfm_score'] < 20:
            return 'critical'
        elif row['recency_days'] > 60 or row['rfm_score'] < 40:
            return 'high'
        elif row['recency_days'] > 30 or row['rfm_score'] < 60:
            return 'medium'
        else:
            return 'low'

    agg['churn_risk'] = agg.apply(churn_bucket, axis=1)
    return agg
```

Celery tasks run this in batches:
- `score_single_customer(customer_id)` — triggered after any order insert or customer create
- `batch_score_all_customers()` — runs nightly via Celery Beat

### Feature 5: Post-Campaign Analyst

Triggered automatically by `finalize_campaign` Celery task.

```python
def generate_postmortem(campaign: dict, stats: dict, segment: dict) -> str:
    prompt = f"""
    You are a marketing analyst. Write a post-campaign analysis in 3–4 sentences.
    Be specific. Include numbers. End with one concrete recommendation.
    
    Campaign: {campaign['name']}
    Segment: {segment['name']} ({stats['total_sent']} customers)
    Channel: {campaign['channel']}
    
    Results:
    - Delivery rate: {stats['delivery_rate']:.1f}%
    - Open rate: {stats['open_rate']:.1f}%
    - Click rate: {stats['click_rate']:.1f}%
    - Failed: {stats['total_failed']}
    
    Write the post-mortem now. Do not use bullet points. Paragraph form only.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()
```

---

## 9. Frontend — All Screens

Built with Next.js 14 App Router + shadcn/ui + Tailwind CSS.

### Screen 1: Dashboard (`/dashboard`)

**Components:**
- `AIBriefingCard` — Morning AI summary: "3 segments are at churn risk this week. 847 customers haven't ordered in 60+ days. Your last campaign had a 66% open rate." Generated fresh via `GET /api/v1/analytics/overview` + Groq call on page load, cached 30 min.
- `MetricGrid` — 4 stat cards: Revenue Influenced (30d), Messages Delivered (30d), Avg Open Rate, Active Campaigns
- `CampaignStatusList` — Last 5 campaigns with status badges and quick-view stats
- `ChurnRiskBreakdown` — Donut chart: Low / Medium / High / Critical customer counts
- `QuickActionCards` — "New Campaign", "Import Customers", "Open Copilot"

### Screen 2: Customers (`/customers`)

**Components:**
- `CustomerTable` — Sortable, filterable table. Columns: Name, City, Orders, Last Order, Total Spend, Churn Risk badge. Pagination. Search bar.
- `ChurnRiskFilter` — Tab bar: All / Low / Medium / High / Critical
- `CustomerDetailSheet` — Slide-in side panel on row click. Shows:
  - AI 360 summary (fetched from `GET /customers/{id}`)
  - Order history table
  - Campaigns they were part of
  - "Message this customer" quick action (creates a one-person campaign)

### Screen 3: Segments (`/segments`)

**Components:**
- `SegmentList` — Cards for each saved segment: name, customer count, last updated
- `NLSegmentBox` — Large text input: "Describe your audience..." → live preview after 500ms debounce
  - Calls `POST /segments/nl2segment`
  - Shows: parsed filter spec as readable chips + "847 customers match" count + preview names
  - "Save as segment" button → opens name dialog → calls `POST /segments`
- `FilterBuilder` — Visual alternative: dropdowns for field + operator + value, AND/OR combinator
  - Real-time count updates as filters change
  - Shares the same filter spec format as NL2Segment
- Both modes are tabs: "Natural Language" (default) | "Filter Builder"

### Screen 4: Campaigns (`/campaigns`)

**Campaign list view:**
- Table with: Name, Segment, Channel, Status badge, Sent/Delivered/Opened/Clicked, Launch date
- "New Campaign" button → opens wizard

**Campaign wizard (multi-step):**

Step 1 — Choose segment (list of saved segments with counts, or "Create new")
Step 2 — Choose channel (WhatsApp / SMS / Email / RCS) with expected open rate shown
Step 3 — Message
  - Text area with `{first_name}`, `{last_product}` variable chips
  - "Generate with AI" button → calls Groq with campaign goal input → fills textarea
  - "Preview personalized" button → shows 3 sample customers with their actual generated messages
Step 4 — Schedule (launch now or pick datetime)
Step 5 — Review & Launch

**Campaign detail view (`/campaigns/{id}`):**
- `DeliveryTracker` — Live stats updating in real-time via Supabase Realtime subscription
  - Progress bars: Sent → Delivered → Opened → Clicked
  - Funnel visualization
  - Failure count with reason breakdown
- `CommunicationsTable` — Per-customer message status (paginated, filterable by status)
- `AIPostmortem` — Rendered when campaign completes (polling `ai_postmortem` field)

### Screen 5: AI Copilot (`/copilot`)

**`CopilotChat` component:**

Full chat interface. Renders different message bubble types:

- Regular text → standard assistant bubble
- `tool_call` event → a step card:
  ```
  ┌─────────────────────────────────────┐
  │ ⚡ Calling get_segments             │
  │   churn_risk_filter: "high"         │
  └─────────────────────────────────────┘
  ```
- `tool_result` event → result card beneath the step card:
  ```
  ┌─────────────────────────────────────┐
  │ ✓ Found 3 segments                  │
  │   • High-value lapsed (847)         │
  │   • Diwali buyers (312)             │
  │   • Recent signups (521)            │
  └─────────────────────────────────────┘
  ```
- Confirmation prompt before launch → inline Yes/No buttons in chat

**`ToolCallTrace` component:**
- Collapsible timeline on the right sidebar showing all tool calls in order
- Each step: tool name, args (collapsed), result summary, duration in ms

**Suggested prompts (shown on empty state):**
- "Re-engage customers who bought last Diwali but went quiet"
- "Find my highest churn risk customers and send them a discount"
- "Who should I target for our weekend sale?"
- "Create a win-back campaign for customers who haven't ordered in 90 days"

### Screen 6: Analytics (`/analytics`)

**Components:**
- `CampaignPerformanceChart` — Line chart: open rate / click rate over last 90 days, one line per campaign
- `ChannelComparison` — Bar chart: WhatsApp vs SMS vs Email vs RCS, grouped by metric
- `TopPerformingCampaigns` — Table sorted by click rate
- `CustomerCohortTable` — Cohort by signup month vs churn risk distribution
- `AIInsightCard` — Weekly AI-generated insight: "Your WhatsApp campaigns consistently outperform Email by 2.3×. Consider migrating your next campaign to WhatsApp."

### Onboarding / Settings (`/settings`)

- **Import Data tab** — CSV upload with column mapping UI, import history, error log
- **API Keys tab** — Generate and manage API keys for programmatic data push
- **Brand Profile tab** — Brand name, default channel, tone preference ("friendly" / "professional" / "urgent")
- **Notifications tab** — Email alerts when campaigns complete or churn risk spikes

---

## 10. Onboarding — How a Startup Uses Orbit

### The Scenario

A new D2C brand (e.g., a specialty coffee subscription startup) creates an account and wants to run their first re-engagement campaign within 15 minutes.

### Step-by-Step Workflow

**Step 1 — Account creation**
Supabase Auth handles signup. On first login, an onboarding checklist is shown:
- [ ] Import customers
- [ ] Import orders
- [ ] Create your first segment
- [ ] Launch your first campaign

**Step 2 — Data ingestion (three paths)**

*Path A — CSV upload (most common):*
1. Marketer goes to Settings → Import Data
2. Uploads `customers.csv` with columns: `external_id, first_name, last_name, phone, email, city`
3. System shows column preview and mapping UI (auto-detects standard column names)
4. Click "Import" → system deduplicates on `external_id` or `phone`
5. Then uploads `orders.csv` with: `external_id, customer_external_id, order_date, amount, category, product_name`
6. Import status shows: "498 customers imported, 2 failed (see errors)"

*Path B — API push (tech-forward brands):*
The startup's backend pushes data directly:
```bash
# Create customers
curl -X POST https://orbit.yourdomain.com/api/v1/customers \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"external_id": "C001", "first_name": "Priya", "phone": "+919876543210", ...}'

# Create orders
curl -X POST https://orbit.yourdomain.com/api/v1/orders \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"customer_id": "uuid", "order_date": "2026-05-01", "amount": 1299, ...}'
```

*Path C — Manual entry:*
For small lists or testing: Settings → Import Data → "Add manually" → form for individual customers.

**Step 3 — Automatic processing (happens in background)**
- Celery task scores all imported customers via RFM model
- `customer_scores` table populated within seconds of import
- Dashboard shows churn risk breakdown immediately

**Step 4 — First segment**
Marketer opens Segments, types: "customers who ordered more than twice but haven't ordered in the last 45 days"
- AI translates → filter spec
- Live count: "312 customers match"
- Preview: "Priya Sharma, Rahul Mehta, Aisha Khan..."
- Click "Save" → name it "Lapsed loyalists"

**Step 5 — First campaign**
- New Campaign → pick "Lapsed loyalists" segment
- Choose WhatsApp
- Click "Generate with AI" → types campaign goal: "Win back lapsed customers with a personal touch"
- AI generates template: "Hey {first_name}, it's been a while since your last {top_category} order. We miss you — here's 10% off to come back. 😊"
- Click "Preview personalized" → sees 3 actual customer messages
- Click "Launch" → confirm

**Step 6 — Watch it work**
- Campaign detail page shows live delivery tracking
- Messages go from `sent → delivered → opened → clicked` in real-time
- After all messages resolve, AI post-mortem appears automatically

---

## 11. Seed Data

`crm/db/seed.py` generates realistic fake data for a **beauty/skincare D2C brand**.

**Generates:**
- 500 customers (Indian names, cities, phone numbers in E.164 format)
- 2,000–4,000 orders spread across 18 months
- Realistic distributions: 20% of customers are churned (90+ days since last order), 30% are high-risk

```python
# Categories for the beauty brand
CATEGORIES = ["skincare", "haircare", "makeup", "fragrance", "bodycare"]

PRODUCTS = {
    "skincare": ["Rose Serum 50ml", "Vitamin C Moisturiser", "Niacinamide Toner", "SPF 50 Sunscreen"],
    "haircare": ["Argan Oil Shampoo", "Deep Condition Mask", "Hair Growth Serum", "Scalp Scrub"],
    "makeup":   ["Matte Lipstick", "Kajal Stick", "Foundation SPF 20", "Setting Spray"],
    "fragrance":["Oud Eau de Parfum", "Rose Mist", "Sandalwood Roll-on"],
    "bodycare": ["Shea Butter Lotion", "Ubtan Scrub", "Kumkumadi Oil"]
}

CITIES = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Pune",
          "Kolkata", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Indore"]

# Run with: python crm/db/seed.py
```

---

## 12. Environment Variables

### CRM Service (`.env` in `crm/`)

```env
# Supabase
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGci...          # service role key (not anon key)

# Groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx

# Redis (Celery broker)
REDIS_URL=redis://localhost:6379/0

# Channel service URL
CHANNEL_SERVICE_URL=http://localhost:8001

# App
PORT=8000
DEBUG=false
SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend.vercel.app
```

### Channel Service (`.env` in `channel/`)

```env
# Redis (same instance as CRM)
REDIS_URL=redis://localhost:6379/0

# CRM receipt callback URL
CRM_RECEIPT_URL=http://localhost:8000/api/v1/receipts

# App
PORT=8001
DEBUG=false
```

### Frontend (`.env.local` in `frontend/`)

```env
NEXT_PUBLIC_CRM_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGci...   # anon key (public, safe for frontend)
```

---

## 13. Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for Redis)

### Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/orbit
cd orbit

# 2. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 3. Set up CRM backend
cd crm
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in your Supabase + Groq keys

# 4. Run Supabase schema
# Go to your Supabase dashboard → SQL editor → paste contents of crm/db/schema.sql

# 5. Seed the database
python db/seed.py

# 6. Start CRM server
uvicorn main:app --reload --port 8000

# 7. Start CRM Celery worker (new terminal)
celery -A celery_app worker --loglevel=info --queues=crm

# 8. Set up Channel service (new terminal)
cd ../channel
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 9. Start Channel server
uvicorn main:app --reload --port 8001

# 10. Start Channel Celery worker (new terminal)
celery -A celery_app worker --loglevel=info --queues=channel

# 11. Start frontend (new terminal)
cd ../frontend
npm install
cp .env.local.example .env.local   # fill in URLs
npm run dev
```

Open `http://localhost:3000`.

### docker-compose (alternative)

```bash
docker-compose up --build
```

The `docker-compose.yml` starts: crm, channel, crm-worker, channel-worker, redis.

---

## 14. Deployment

### Render (CRM + Channel services)

1. Create a new **Web Service** for `crm/`: build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`
2. Create a **Background Worker** for CRM Celery: same build, start command `celery -A celery_app worker --loglevel=info --queues=crm`
3. Create a new **Web Service** for `channel/`: same pattern, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Create a **Background Worker** for Channel Celery: `celery -A celery_app worker --loglevel=info --queues=channel`
5. Create a **Redis** instance on Render, copy the `REDIS_URL`
6. Add all environment variables in the Render dashboard for each service

### Vercel (Frontend)

```bash
cd frontend
vercel deploy --prod
```

Add environment variables in the Vercel dashboard.

---

## 15. Scale Assumptions & Tradeoffs

### What I assumed for this scope

- **Single tenant** — one brand per deployment. No multi-tenancy row-level security. At scale: add `brand_id` FK to all tables and enable Supabase RLS policies.
- **Celery with Redis** — sufficient for hundreds of concurrent campaigns. At scale: migrate to AWS SQS or Celery with RabbitMQ for durability guarantees.
- **Sync LLM calls in API layer** — NL2Segment is synchronous (fast on Groq ~200ms). Personalization for large segments runs in a Celery task. At scale: all LLM calls should be async tasks.
- **Groq free tier** — rate limited at ~30 requests/min. For production: add a simple queue in front of all Groq calls to respect rate limits, or upgrade to paid tier / self-host Llama via vLLM.
- **Supabase free tier** — 500MB database, 2GB egress. Sufficient for demo. At scale: dedicated Postgres with read replicas for analytics queries.
- **RFM scoring in pandas** — works up to ~1M customers in memory. At scale: push computation to PostgreSQL via `GROUP BY` + window functions, or use a scheduled dbt model.
- **No auth** — Supabase Auth is wired up for login/logout but there's no role-based access control. At scale: add `admin` / `marketer` / `viewer` roles.
- **No rate limiting on `/receipts`** — the channel service callback endpoint is open. At scale: add API key auth on receipts + IP allowlist to only accept from the channel service.
- **Receipt ordering** — a `delivered` callback could arrive before `sent` if Redis jobs are out of order. Handled by: the receipt handler checks current status and only advances forward (a `clicked` event does not regress a `failed` status). The `idempotency_key` prevents double-counting.

### Conscious cuts

- No real messaging provider integration (as per assignment spec)
- No A/B testing on messages (would require splitting the segment and creating two sub-campaigns)
- No unsubscribe handling (real product needs opt-out tracking per channel per customer)
- No email templates (HTML email composition is a feature on its own)
- Analytics cohort analysis is simplified (full cohort analysis would use window functions with date_trunc)
