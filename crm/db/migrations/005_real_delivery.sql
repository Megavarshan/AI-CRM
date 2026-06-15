-- ============================================================
-- Migration 005 — Real delivery (email opt-out, subjects, CTA)
-- Paste into the Supabase SQL Editor and Run. Idempotent.
-- ============================================================

-- Unsubscribe / suppression for real email sending (compliance).
ALTER TABLE customers ADD COLUMN IF NOT EXISTS email_opt_out BOOLEAN NOT NULL DEFAULT FALSE;

-- Email subject line per recipient.
ALTER TABLE communications ADD COLUMN IF NOT EXISTS subject TEXT;

-- Campaign call-to-action destination (click-tracked). Falls back to org website.
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cta_url TEXT;
