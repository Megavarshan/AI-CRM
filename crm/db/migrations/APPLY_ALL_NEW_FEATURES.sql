-- ============================================================
-- Orbit — apply ALL new-feature migrations in one go.
-- Paste this whole file into the Supabase SQL Editor and Run.
-- Safe to run more than once (idempotent).
-- ============================================================

-- ── 002: organizations (auth) ───────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          TEXT UNIQUE NOT NULL,
  company_name    TEXT NOT NULL,
  customer_size   TEXT,
  turnover        TEXT,
  city            TEXT,
  country         TEXT,
  website         TEXT,
  password_hash   TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_organizations_org_id ON organizations(org_id);

-- ── 003: multi-tenancy + campaign feedback ──────────────────
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS industry TEXT;

ALTER TABLE customers       ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE orders          ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE segments        ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE campaigns       ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE communications  ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE customer_scores ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_customers_org      ON customers(org_id);
CREATE INDEX IF NOT EXISTS idx_orders_org         ON orders(org_id);
CREATE INDEX IF NOT EXISTS idx_segments_org       ON segments(org_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_org      ON campaigns(org_id);
CREATE INDEX IF NOT EXISTS idx_communications_org ON communications(org_id);
CREATE INDEX IF NOT EXISTS idx_scores_org         ON customer_scores(org_id);

-- Per-org uniqueness (was global)
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_external_id_key;
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_phone_key;
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_email_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_org_external
  ON customers(org_id, external_id) WHERE external_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_org_phone
  ON customers(org_id, phone) WHERE phone IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_org_email
  ON customers(org_id, email) WHERE email IS NOT NULL;

-- Campaign feedback (Human-in-the-Loop learning)
CREATE TABLE IF NOT EXISTS campaign_feedback (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  rating          INTEGER CHECK (rating BETWEEN 1 AND 5),
  business_impact TEXT,
  comments        TEXT,
  submitted_by    TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_org      ON campaign_feedback(org_id);
CREATE INDEX IF NOT EXISTS idx_feedback_campaign ON campaign_feedback(campaign_id);
