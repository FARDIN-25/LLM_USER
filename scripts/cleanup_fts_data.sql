-- ============================================
-- PHASE 2: DATA CLEANING & FTS REBUILD
-- Safe Incremental Execution
-- ============================================

-- STEP 1: ADD CLEAN COLUMN (IF NOT EXISTS)
-- Using a flag is safer than deletion in production environments
ALTER TABLE docs_chunks ADD COLUMN IF NOT EXISTS is_clean BOOLEAN DEFAULT TRUE;
ALTER TABLE book_chunks ADD COLUMN IF NOT EXISTS is_clean BOOLEAN DEFAULT TRUE;

-- STEP 2: FLAG NOISY DATA (INCREMENTAL)
-- We set is_clean = FALSE for rows that match our 'noise' criteria
-- This preserves the data but allows the application to filter it out

-- Flagging docs_chunks
UPDATE docs_chunks
SET is_clean = FALSE
WHERE 
    length(chunk_text) < 100                                    -- Too short
    OR chunk_text ~ '^[A-Z0-9\s[:punct:]]+$'                    -- OCR noise
    OR lower(chunk_text) LIKE '%form gst%'                      -- Forms
    OR lower(chunk_text) LIKE '%preface%'                       -- Metadata
    OR lower(chunk_text) LIKE '%table of contents%'             -- Table of contents
    OR NOT (lower(chunk_text) ~ 'gst|tax|bhaaskar');           -- Non-relevant

-- Flagging book_chunks
UPDATE book_chunks
SET is_clean = FALSE
WHERE 
    length(chunk_text) < 100 
    OR chunk_text ~ '^[A-Z0-9\s[:punct:]]+$'
    OR lower(chunk_text) LIKE '%preface%'
    OR lower(chunk_text) LIKE '%index%'
    OR NOT (lower(chunk_text) ~ 'gst|tax|bhaaskar');

-- STEP 3: REBUILD FTS ONLY FOR CLEAN DATA (OPTIONAL)
-- This makes FTS queries faster by ignoring noisy rows
-- Uncomment the following if you want FTS to strictly ignore 'dirty' data
/*
UPDATE docs_chunks 
SET fts_vector = to_tsvector('english', chunk_text) 
WHERE is_clean = TRUE;

UPDATE docs_chunks 
SET fts_vector = ''::tsvector 
WHERE is_clean = FALSE;
*/

-- STEP 4: OPTIMIZE
ANALYZE docs_chunks;
ANALYZE book_chunks;

-- STEP 5: VERIFICATION
-- View how many rows were flagged as dirty
SELECT 
    'docs_chunks' as table_name, 
    count(*) filter (where is_clean = TRUE) as clean_count,
    count(*) filter (where is_clean = FALSE) as noisy_count
FROM docs_chunks
UNION ALL
SELECT 
    'book_chunks' as table_name, 
    count(*) filter (where is_clean = TRUE) as clean_count,
    count(*) filter (where is_clean = FALSE) as noisy_count
FROM book_chunks;
