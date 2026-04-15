-- m:\LLM\llm-user-service-main\src\db_service\migrations\rag_standardization.sql

-- 1. Backup before deletion (Safety)
CREATE TABLE IF NOT EXISTS document_chunks_backup AS 
SELECT * FROM document_chunks;

-- 2. Drop the redundant table
DROP TABLE IF EXISTS document_chunks;

-- 3. Standardize Remaining Tables (Ensure columns match)
-- docs_chunks: already has most fields, but ensuring consistency
ALTER TABLE docs_chunks ADD COLUMN IF NOT EXISTS fts_vector TSVECTOR;
ALTER TABLE book_chunks ADD COLUMN IF NOT EXISTS fts_vector TSVECTOR;

-- 4. Fix FTS Configuration (Using 'simple' for GST domain terms)
-- Create stored generated columns for performance if not already exist
-- We use a trigger or manual update as some PG versions don't support stored generated vectors easily with complex models
-- For simplicity in this env, we update existing rows and ensure the code updates new ones.

UPDATE docs_chunks SET fts_vector = to_tsvector('simple', COALESCE(chunk_text, ''));
UPDATE book_chunks SET fts_vector = to_tsvector('simple', COALESCE(chunk_text, ''));

-- 5. Add FTS Indexes (GIN)
CREATE INDEX IF NOT EXISTS idx_docs_fts ON docs_chunks USING GIN(fts_vector);
CREATE INDEX IF NOT EXISTS idx_books_fts ON book_chunks USING GIN(fts_vector);

-- 6. Add Vector Indexes (IVFFLAT for Cosine Similarity)
-- Assumes pgvector is enabling
-- Using ivfflat with cosine_ops as requested
CREATE INDEX IF NOT EXISTS idx_docs_vector ON docs_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_books_vector ON book_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 7. Log completion
DO $$ 
BEGIN 
    RAISE NOTICE 'RAG Standardization Complete: context tables synchronized, legacy table removed.'; 
END $$;
