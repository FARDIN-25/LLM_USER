
import sys
import os
import time
from sqlalchemy import text, create_engine
from sqlalchemy.engine import url as engine_url

# Attempt to get DATABASE_URL from config or env
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.shared.config import settings

def get_engine():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
    return create_engine(db_url)

def run_phase(engine, phase_name, sql):
    print(f"\n>>> RUNNING PHASE: {phase_name}")
    start = time.time()
    with engine.connect() as conn:
        with conn.begin():
            res = conn.execute(text(sql))
            if res.returns_rows:
                rows = res.fetchall()
                for r in rows:
                    print(f"  {r}")
    print(f"--- Completed in {time.time() - start:.2f}s ---")

def apply_refactor():
    engine = get_engine()
    
    # PHASE 0: BACKUP
    run_phase(engine, "0: BACKUP", "CREATE TABLE IF NOT EXISTS book_chunks_backup AS SELECT * FROM book_chunks;")
    
    # PHASE 1: ADD CLEAN TEXT COLUMN
    run_phase(engine, "1: ADD CLEAN TEXT COLUMN", "ALTER TABLE book_chunks ADD COLUMN IF NOT EXISTS clean_text TEXT;")
    
    # PHASE 2: CLEAN EXISTING TEXT DATA
    run_phase(engine, "2: CLEAN DATA", """
        UPDATE book_chunks
        SET clean_text = LOWER(REGEXP_REPLACE(chunk_text, '[^a-zA-Z0-9\s]', ' ', 'g'));
    """)
    
    # PHASE 3: VERIFY
    run_phase(engine, "3: VERIFY", "SELECT chunk_text, clean_text FROM book_chunks LIMIT 5;")
    
    # PHASE 4: NOISE REMOVAL
    run_phase(engine, "4: NOISE REMOVAL", """
        DELETE FROM book_chunks
        WHERE clean_text LIKE '%preface%'
           OR clean_text LIKE '%appendix%'
           OR clean_text LIKE '%form gst%'
           OR clean_text LIKE '%section%'
           OR LENGTH(clean_text) < 100;
    """)
    
    # PHASE 5: REBUILD FTS
    run_phase(engine, "5: REBUILD FTS", "UPDATE book_chunks SET fts_vector = TO_TSVECTOR('english', clean_text);")
    
    # PHASE 6: REINDEX
    run_phase(engine, "6: REINDEX", "REINDEX TABLE book_chunks;")
    
    # PHASE 7: VALIDATION
    run_phase(engine, "7: VALIDATION", "SELECT chunk_text FROM book_chunks WHERE fts_vector @@ plainto_tsquery('english', 'gst') LIMIT 3;")

if __name__ == "__main__":
    try:
        apply_refactor()
        print("\n[SUCCESS] All phases completed successfully.")
    except Exception as e:
        print(f"\n[ERROR] Refactor failed: {e}")
        sys.exit(1)
