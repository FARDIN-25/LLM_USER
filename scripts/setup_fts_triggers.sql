-- ============================================
-- AUTOMATED FTS SYNCHRONIZATION SCRIPT
-- Purpose: Automatic cleaning and indexing on update
-- ============================================

-- STEP 1: SCHEMA CONSISTENCY
-- Ensure both tables have the necessary columns
ALTER TABLE docs_chunks ADD COLUMN IF NOT EXISTS clean_text TEXT;
ALTER TABLE book_chunks ADD COLUMN IF NOT EXISTS clean_text TEXT;
ALTER TABLE docs_chunks ADD COLUMN IF NOT EXISTS is_clean BOOLEAN DEFAULT TRUE;
ALTER TABLE book_chunks ADD COLUMN IF NOT EXISTS is_clean BOOLEAN DEFAULT TRUE;

-- STEP 2: CREATE TRIGGER FUNCTION
-- This function will run before every INSERT or UPDATE
CREATE OR REPLACE FUNCTION sync_fts_data_fn() 
RETURNS trigger AS $$
BEGIN
    -- 1. Generate Clean Text (Lowercase, remove symbols)
    NEW.clean_text := LOWER(REGEXP_REPLACE(NEW.chunk_text, '[^a-zA-Z0-9\s]', ' ', 'g'));
    
    -- 2. Force mark as clean (since it just went through the filter)
    NEW.is_clean := TRUE;
    
    -- 3. Update FTS Vector from the cleaned text
    NEW.fts_vector := TO_TSVECTOR('english', COALESCE(NEW.clean_text, ''));
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- STEP 3: APPLY TRIGGERS
-- Remove existing triggers if they exist to avoid duplicates
DROP TRIGGER IF EXISTS trg_sync_docs_fts ON docs_chunks;
DROP TRIGGER IF EXISTS trg_sync_book_fts ON book_chunks;

-- Apply to docs_chunks
CREATE TRIGGER trg_sync_docs_fts
BEFORE INSERT OR UPDATE OF chunk_text ON docs_chunks
FOR EACH ROW EXECUTE FUNCTION sync_fts_data_fn();

-- Apply to book_chunks
CREATE TRIGGER trg_sync_book_fts
BEFORE INSERT OR UPDATE OF chunk_text ON book_chunks
FOR EACH ROW EXECUTE FUNCTION sync_fts_data_fn();

-- STEP 4: RETROACTIVE SYNC (OPTIONAL)
-- If there are rows without clean_text, sync them now
UPDATE docs_chunks SET chunk_text = chunk_text WHERE clean_text IS NULL;
UPDATE book_chunks SET chunk_text = chunk_text WHERE clean_text IS NULL;

-- STEP 5: VERIFICATION
SELECT 
    'docs_chunks' as table_name, count(*) as total, 
    count(clean_text) as synced_clean, 
    count(fts_vector) as synced_vector
FROM docs_chunks
UNION ALL
SELECT 
    'book_chunks' as table_name, count(*) as total, 
    count(clean_text) as synced_clean, 
    count(fts_vector) as synced_vector
FROM book_chunks;
