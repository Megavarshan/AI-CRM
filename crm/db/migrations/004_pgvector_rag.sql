-- ============================================================
-- Migration 004 — pgvector RAG layer (semantic customer search)
-- Paste into the Supabase SQL Editor and Run. Idempotent.
-- ============================================================

-- 1. Enable the vector extension (Supabase ships it).
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Embedding column on customers (bge-small-en-v1.5 = 384 dims).
ALTER TABLE customers ADD COLUMN IF NOT EXISTS embedding vector(384);

-- 3. Approximate-nearest-neighbour index (cosine), HNSW.
--    HNSW builds incrementally (no "built on empty column" recall problem like
--    ivfflat) and has excellent recall — the right choice for production.
CREATE INDEX IF NOT EXISTS idx_customers_embedding
  ON customers USING hnsw (embedding vector_cosine_ops);

-- 4. Org-scoped similarity search RPC.
--    query_embedding is passed as a pgvector text literal ('[...]') and cast,
--    which avoids JSON-array → vector coercion issues over PostgREST.
CREATE OR REPLACE FUNCTION match_customers(
  query_embedding TEXT,
  match_org       UUID DEFAULT NULL,
  match_count     INT  DEFAULT 10
)
RETURNS TABLE (
  id           UUID,
  first_name   TEXT,
  last_name    TEXT,
  city         TEXT,
  channel_pref TEXT,
  similarity   FLOAT
)
LANGUAGE sql STABLE AS $$
  SELECT c.id, c.first_name, c.last_name, c.city, c.channel_pref,
         1 - (c.embedding <=> query_embedding::vector(384)) AS similarity
  FROM customers c
  WHERE c.embedding IS NOT NULL
    AND (match_org IS NULL OR c.org_id = match_org)
  ORDER BY c.embedding <=> query_embedding::vector(384)
  LIMIT match_count;
$$;

-- 5. Lookalike: nearest neighbours to an existing customer (same org), excluding self.
CREATE OR REPLACE FUNCTION similar_customers(
  source_id    UUID,
  match_org    UUID DEFAULT NULL,
  match_count  INT  DEFAULT 8
)
RETURNS TABLE (
  id           UUID,
  first_name   TEXT,
  last_name    TEXT,
  city         TEXT,
  channel_pref TEXT,
  similarity   FLOAT
)
LANGUAGE sql STABLE AS $$
  WITH src AS (SELECT embedding FROM customers WHERE id = source_id)
  SELECT c.id, c.first_name, c.last_name, c.city, c.channel_pref,
         1 - (c.embedding <=> (SELECT embedding FROM src)) AS similarity
  FROM customers c, src
  WHERE c.embedding IS NOT NULL
    AND c.id <> source_id
    AND (match_org IS NULL OR c.org_id = match_org)
    AND (SELECT embedding FROM src) IS NOT NULL
  ORDER BY c.embedding <=> (SELECT embedding FROM src)
  LIMIT match_count;
$$;
