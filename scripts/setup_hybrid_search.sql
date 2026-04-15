-- ============================================
-- HYBRID SEARCH SETUP (pgvector)
-- ============================================

-- STEP 1: ENABLE EXTENSION
CREATE EXTENSION IF NOT EXISTS vector;

-- STEP 2: ADD EMBEDDING COLUMNS
-- Dimensions: 384 (Match all-MiniLM-L6-v2)
ALTER TABLE docs_chunks ADD COLUMN IF NOT EXISTS embedding vector(384);
ALTER TABLE book_chunks ADD COLUMN IF NOT EXISTS embedding vector(384);

-- STEP 3: CREATE VECTOR INDICES (IVFFlat)
-- For performance on larger datasets
CREATE INDEX IF NOT EXISTS idx_docs_chunks_embedding 
ON docs_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_book_chunks_embedding 
ON book_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- STEP 4: VERIFICATION
SELECT 
    table_name, column_name, data_type, udt_name 
FROM information_schema.columns 
WHERE table_name IN ('docs_chunks', 'book_chunks') 
  AND column_name = 'embedding';
