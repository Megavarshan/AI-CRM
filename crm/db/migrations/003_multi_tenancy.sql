-- ============================================================
-- Migration 003 — Multi-tenancy, Campaign Feedback
-- Run this in the Supabase SQL Editor (after 002_organizations.sql).
-- Idempotent: safe to run more than once.
-- ============================================================

-- ── organizations: extra column ─────────────────────────────
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS industry TEXT;

-- ── org_id on every core entity ─────────────────────────────
ALTER TABLE customers      ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE orders         ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE segments       ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE campaigns      ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE communications ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE customer_scores ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_customers_org      ON customers(org_id);
CREATE INDEX IF NOT EXISTS idx_orders_org         ON orders(org_id);
CREATE INDEX IF NOT EXISTS idx_segments_org       ON segments(org_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_org      ON campaigns(org_id);
CREATE INDEX IF NOT EXISTS idx_communications_org ON communications(org_id);
CREATE INDEX IF NOT EXISTS idx_scores_org         ON customer_scores(org_id);

-- Backfill customer_scores.org_id from its customer (existing rows).
UPDATE customer_scores cs SET org_id = c.org_id
  FROM customers c WHERE cs.customer_id = c.id AND cs.org_id IS NULL;

-- ── Per-org uniqueness (was global) ─────────────────────────
-- A customer's external_id / phone / email only needs to be unique
-- within its own organization in a multi-tenant world.
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_external_id_key;
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_phone_key;
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_email_key;

DROP INDEX IF EXISTS uq_customers_org_external;
CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_org_external
  ON customers(org_id, external_id) WHERE external_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_org_phone
  ON customers(org_id, phone) WHERE phone IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_org_email
  ON customers(org_id, email) WHERE email IS NOT NULL;

-- ── campaign_feedback (Human-in-the-Loop learning) ──────────
CREATE TABLE IF NOT EXISTS campaign_feedback (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  rating          INTEGER CHECK (rating BETWEEN 1 AND 5),
  business_impact TEXT,        -- e.g. 'high_sales' | 'some_sales' | 'no_impact' | 'negative'
  comments        TEXT,
  submitted_by    TEXT,        -- org_id string or 'admin'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_org      ON campaign_feedback(org_id);
CREATE INDEX IF NOT EXISTS idx_feedback_campaign ON campaign_feedback(campaign_id);

-- ── Atomic counter RPC: scope to org-safe (re-create, unchanged behavior) ──
-- (increment_campaign_counter already exists from schema.sql)
