-- Runs once on first database initialization (docker-entrypoint-initdb.d).
-- Alembic also creates these idempotently; this makes a fresh box ready immediately.
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector: embeddings + HNSW
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy keyword complement
CREATE EXTENSION IF NOT EXISTS unaccent;   -- diacritic folding helper
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive email column
