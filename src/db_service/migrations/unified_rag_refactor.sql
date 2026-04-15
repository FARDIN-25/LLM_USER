-- Migration: Unified RAG Refactor & document_chunks Deprecation

-- 1. Migrate history column to TEXT[] for prefixed IDs
ALTER TABLE query_responses 
ALTER COLUMN retrieved_context_ids TYPE TEXT[] 
USING retrieved_context_ids::TEXT[];

-- 2. Add chunk_hash to active tables for SHA-256 deduplication
ALTER TABLE docs_chunks ADD COLUMN IF NOT EXISTS chunk_hash VARCHAR(64);
ALTER TABLE book_chunks ADD COLUMN IF NOT EXISTS chunk_hash VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_docs_chunk_hash ON docs_chunks (chunk_hash);
CREATE INDEX IF NOT EXISTS idx_book_chunk_hash ON book_chunks (chunk_hash);

-- 3. Deprecate document_chunks (Archival only)
COMMENT ON TABLE document_chunks IS 'DEPRECATED: Retained for archival purposes only. Do not use in active code paths.';
REVOKE INSERT, UPDATE, DELETE ON document_chunks FROM PUBLIC;

-- 4. Optimize Indexes
-- Ensure pgvector extension is present
CREATE EXTENSION IF NOT EXISTS vector;

-- GIN Indexes for Full-Text Search
CREATE INDEX IF NOT EXISTS idx_docs_fts ON docs_chunks USING GIN (fts_vector);
CREATE INDEX IF NOT EXISTS idx_books_fts ON book_chunks USING GIN (fts_vector);

-- IVFFLAT Indexes for Vector Search (Cosine Similarity)
-- Note: Dimensions must match. Assuming 384 based on models.py
CREATE INDEX IF NOT EXISTS idx_docs_embedding_cosine ON docs_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_books_embedding_cosine ON book_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 5. Final Analytics Activation
ANALYZE docs_chunks;
ANALYZE book_chunks;
