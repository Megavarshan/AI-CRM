-- ============================================================
-- Migration 002 — Organizations (org signup/login)
-- Run this in the Supabase SQL Editor.
-- ============================================================

CREATE TABLE IF NOT EXISTS organizations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          TEXT UNIQUE NOT NULL,          -- human-friendly login ID e.g. ORB-7F3K2A
  company_name    TEXT NOT NULL,
  customer_size   TEXT,                          -- e.g. '<1k', '1k-10k', '10k-100k', '100k+'
  turnover        TEXT,                          -- annual turnover bracket (free text)
  city            TEXT,
  country         TEXT,
  website         TEXT,
  password_hash   TEXT NOT NULL,                 -- pbkdf2$<iterations>$<salt>$<hash>
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_organizations_org_id ON organizations(org_id);
