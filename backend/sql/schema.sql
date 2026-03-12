-- =============================================================================
-- Personal Context Engine — Supabase Schema
-- Run this entire file in: Supabase Dashboard → SQL Editor → New query
-- =============================================================================

-- ── Step 1: Enable the pgvector extension ────────────────────────────────────
-- Required for storing and searching vector embeddings.
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Step 2: Prepare the vecs schema ──────────────────────────────────────────
-- The Python `vecs` library (used by llama-index-vector-stores-supabase)
-- stores embedding collections here. It will auto-create collection tables
-- when ingest.py runs, but we create the schema now to be safe.
CREATE SCHEMA IF NOT EXISTS vecs;

-- Grant the service role access to vecs schema
GRANT USAGE ON SCHEMA vecs TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA vecs TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA vecs GRANT ALL ON TABLES TO service_role;

-- ── Step 3: Document metadata table ──────────────────────────────────────────
-- Stores high-level metadata about each INGESTED FILE (not individual chunks).
-- Chunks and their embeddings live in the vecs collection managed by LlamaIndex.
CREATE TABLE IF NOT EXISTS public.documents_metadata (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT        NOT NULL,              -- file path, email address, etc.
    doc_type    TEXT        NOT NULL DEFAULT 'txt',-- 'txt', 'email', 'chat', 'csv', 'json'
    title       TEXT,                              -- optional human-readable title
    extra       JSONB       NOT NULL DEFAULT '{}', -- arbitrary extra metadata
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast lookups by source and type
CREATE INDEX IF NOT EXISTS idx_documents_metadata_source
    ON public.documents_metadata (source);
CREATE INDEX IF NOT EXISTS idx_documents_metadata_doc_type
    ON public.documents_metadata (doc_type);

-- ── Step 4: (Reference) What vecs auto-creates ───────────────────────────────
-- When ingest.py calls vecs_client.get_or_create_collection("documents", dim=384),
-- the vecs library will automatically execute something like:
--
-- CREATE TABLE vecs.documents (
--     id       TEXT PRIMARY KEY,
--     vec      VECTOR(384),   -- dimension matches BAAI/bge-small-en-v1.5
--     metadata JSONB NOT NULL DEFAULT '{}'
-- );
-- CREATE INDEX ON vecs.documents USING ivfflat (vec vector_cosine_ops)
--     WITH (lists = 100);
--
-- You do NOT need to run this manually — it is shown here for reference only.
