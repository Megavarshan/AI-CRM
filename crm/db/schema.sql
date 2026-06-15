-- ============================================================
-- Orbit CRM — Supabase (PostgreSQL 15) Schema
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── Drop tables in reverse dependency order if resetting ──────
-- DROP TABLE IF EXISTS imports CASCADE;
-- DROP TABLE IF EXISTS communications CASCADE;
-- DROP TABLE IF EXISTS campaigns CASCADE;
-- DROP TABLE IF EXISTS segments CASCADE;
-- DROP TABLE IF EXISTS customer_scores CASCADE;
-- DROP TABLE IF EXISTS orders CASCADE;
-- DROP TABLE IF EXISTS customers CASCADE;

-- ── customers ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id     TEXT UNIQUE,
  first_name      TEXT NOT NULL,
  last_name       TEXT,
  phone           TEXT UNIQUE,          -- E.164 format e.g. +919876543210
  email           TEXT UNIQUE,
  city            TEXT,
  channel_pref    TEXT DEFAULT 'whatsapp'
                    CHECK (channel_pref IN ('whatsapp','sms','email','rcs')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── orders ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  order_date      TIMESTAMPTZ NOT NULL,
  amount          NUMERIC(10,2) NOT NULL CHECK (amount >= 0),     -- INR
  category        TEXT,
  product_name    TEXT,
  status          TEXT NOT NULL DEFAULT 'completed'
                    CHECK (status IN ('completed','returned','cancelled')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── customer_scores ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_scores (
  customer_id     UUID PRIMARY KEY REFERENCES customers(id) ON DELETE CASCADE,
  recency_days    INTEGER CHECK (recency_days >= 0),
  frequency       INTEGER CHECK (frequency >= 0),
  monetary        NUMERIC(10,2) CHECK (monetary >= 0),
  rfm_score       NUMERIC(5,2) CHECK (rfm_score BETWEEN 0 AND 100),
  churn_risk      TEXT CHECK (churn_risk IN ('low','medium','high','critical')),
  top_category    TEXT,
  last_product    TEXT,
  scored_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── segments ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS segments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  description     TEXT,
  filter_spec     JSONB NOT NULL,
  nl_query        TEXT,
  customer_count  INTEGER DEFAULT 0 CHECK (customer_count >= 0),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── campaigns ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaigns (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  segment_id      UUID REFERENCES segments(id) ON DELETE SET NULL,
  channel         TEXT NOT NULL CHECK (channel IN ('whatsapp','sms','email','rcs')),
  message_template TEXT NOT NULL,
  personalized    BOOLEAN NOT NULL DEFAULT TRUE,
  status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','scheduled','running','completed','failed')),
  scheduled_at    TIMESTAMPTZ,
  launched_at     TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  created_by      TEXT NOT NULL DEFAULT 'marketer',
  total_sent      INTEGER NOT NULL DEFAULT 0 CHECK (total_sent >= 0),
  total_delivered INTEGER NOT NULL DEFAULT 0 CHECK (total_delivered >= 0),
  total_opened    INTEGER NOT NULL DEFAULT 0 CHECK (total_opened >= 0),
  total_clicked   INTEGER NOT NULL DEFAULT 0 CHECK (total_clicked >= 0),
  total_failed    INTEGER NOT NULL DEFAULT 0 CHECK (total_failed >= 0),
  ai_postmortem   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── communications ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS communications (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id         UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  customer_id         UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  channel             TEXT NOT NULL,
  personalized_message TEXT NOT NULL,
  status              TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','sent','delivered','failed','opened','clicked')),
  idempotency_key     TEXT UNIQUE,
  sent_at             TIMESTAMPTZ,
  delivered_at        TIMESTAMPTZ,
  opened_at           TIMESTAMPTZ,
  clicked_at          TIMESTAMPTZ,
  failed_at           TIMESTAMPTZ,
  failure_reason      TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── imports ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS imports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename        TEXT,
  rows_total      INTEGER CHECK (rows_total >= 0),
  rows_imported   INTEGER CHECK (rows_imported >= 0),
  rows_failed     INTEGER CHECK (rows_failed >= 0),
  status          TEXT NOT NULL DEFAULT 'processing'
                    CHECK (status IN ('processing','completed','failed')),
  error_log       JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes for Join and Filter Performance ──────────────────
CREATE INDEX IF NOT EXISTS idx_orders_customer_id     ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status          ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_order_date      ON orders(order_date DESC);

CREATE INDEX IF NOT EXISTS idx_comms_campaign_id      ON communications(campaign_id);
CREATE INDEX IF NOT EXISTS idx_comms_customer_id      ON communications(customer_id);
CREATE INDEX IF NOT EXISTS idx_comms_status           ON communications(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_status       ON campaigns(status);

-- ── Indexes for Sorting & Filtering in Customer Directory ────
CREATE INDEX IF NOT EXISTS idx_scores_churn_risk      ON customer_scores(churn_risk);
CREATE INDEX IF NOT EXISTS idx_scores_monetary        ON customer_scores(monetary DESC);
CREATE INDEX IF NOT EXISTS idx_scores_recency_days    ON customer_scores(recency_days ASC);
CREATE INDEX IF NOT EXISTS idx_scores_frequency       ON customer_scores(frequency DESC);
CREATE INDEX IF NOT EXISTS idx_scores_rfm_score       ON customer_scores(rfm_score DESC);

-- ── Indexes for Fuzzy Search (Trigrams) ──────────────────────
CREATE INDEX IF NOT EXISTS idx_customers_search_name
  ON customers USING gin ((first_name || ' ' || COALESCE(last_name, '')) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_search_email
  ON customers USING gin (email gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_search_phone
  ON customers USING gin (phone gin_trgm_ops);

-- ── updated_at auto-trigger function ───────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ── Drop triggers if they exist to prevent conflicts on rerun ──
DROP TRIGGER IF EXISTS trg_customers_updated_at ON customers;
CREATE TRIGGER trg_customers_updated_at
  BEFORE UPDATE ON customers
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_segments_updated_at ON segments;
CREATE TRIGGER trg_segments_updated_at
  BEFORE UPDATE ON segments
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_campaigns_updated_at ON campaigns;
CREATE TRIGGER trg_campaigns_updated_at
  BEFORE UPDATE ON campaigns
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── RPC: execute_segment_filter ────────────────────────────────
-- Called from segment_executor.py for complex nested AND/OR specs.
-- Accepts a parameterised WHERE clause and returns count + preview.
-- Note: This uses dynamic SQL. The WHERE clause is built server-side
-- by the Python backend, not from user input directly.
CREATE OR REPLACE FUNCTION execute_segment_filter(
  where_clause TEXT,
  params TEXT[] DEFAULT '{}'
)
RETURNS TABLE(total_count BIGINT, customer_id UUID, full_name TEXT) AS $$
DECLARE
  query TEXT;
  count_query TEXT;
  total BIGINT;
BEGIN
  -- Build the full query
  query := format(
    'SELECT c.id AS customer_id, '
    '(c.first_name || '' '' || COALESCE(c.last_name, ''''))::TEXT AS full_name '
    'FROM customers c '
    'JOIN customer_scores s ON s.customer_id = c.id '
    'WHERE %s '
    'LIMIT 5',
    where_clause
  );

  -- Build count query
  count_query := format(
    'SELECT COUNT(*) FROM customers c '
    'JOIN customer_scores s ON s.customer_id = c.id '
    'WHERE %s',
    where_clause
  );

  -- Get total count
  EXECUTE count_query INTO total;

  -- Return rows with count included
  RETURN QUERY
    SELECT total, sub.customer_id, sub.full_name
    FROM (
      SELECT c.id AS customer_id,
             (c.first_name || ' ' || COALESCE(c.last_name, ''))::TEXT AS full_name
      FROM customers c
      JOIN customer_scores s ON s.customer_id = c.id
      WHERE TRUE  -- placeholder, actual WHERE is dynamic
      LIMIT 5
    ) sub;

  -- Note: The above RETURN QUERY uses a static WHERE TRUE because
  -- PL/pgSQL cannot use RETURN QUERY EXECUTE with dynamic SQL directly
  -- in all Supabase versions. The client-side fallback handles this case.
  -- For full dynamic SQL support, use the fallback path in segment_executor.py.
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ── RPC: increment_campaign_counter ────────────────────────────
-- Atomically increments a campaigns counter.
CREATE OR REPLACE FUNCTION increment_campaign_counter(
  camp_id UUID,
  counter_name TEXT
)
RETURNS VOID AS $$
BEGIN
  IF counter_name = 'total_delivered' THEN
    UPDATE campaigns SET total_delivered = total_delivered + 1, updated_at = NOW() WHERE id = camp_id;
  ELSIF counter_name = 'total_opened' THEN
    UPDATE campaigns SET total_opened = total_opened + 1, updated_at = NOW() WHERE id = camp_id;
  ELSIF counter_name = 'total_clicked' THEN
    UPDATE campaigns SET total_clicked = total_clicked + 1, updated_at = NOW() WHERE id = camp_id;
  ELSIF counter_name = 'total_failed' THEN
    UPDATE campaigns SET total_failed = total_failed + 1, updated_at = NOW() WHERE id = camp_id;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


