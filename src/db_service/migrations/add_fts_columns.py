"""
Migration: Add persistent fts_vector column and GIN index to docs_chunks and book_chunks.
This uses PostgreSQL 12+ generated columns.
"""
import logging
from sqlalchemy import text

logger = logging.getLogger("fintax")

MIGRATIONS = [
    # docs_chunks
    {
        "table": "docs_chunks",
        "sql": [
            "ALTER TABLE docs_chunks ADD COLUMN IF NOT EXISTS fts_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED;",
            "CREATE INDEX IF NOT EXISTS ix_docs_chunks_fts_vector ON docs_chunks USING GIN (fts_vector);"
        ]
    },
    # book_chunks
    {
        "table": "book_chunks",
        "sql": [
            "ALTER TABLE book_chunks ADD COLUMN IF NOT EXISTS fts_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED;",
            "CREATE INDEX IF NOT EXISTS ix_book_chunks_fts_vector ON book_chunks USING GIN (fts_vector);"
        ]
    }
]

def run(engine):
    """Apply migrations. Safe to run multiple times."""
    with engine.connect() as conn:
        for migration in MIGRATIONS:
            table = migration["table"]
            for query in migration["sql"]:
                try:
                    conn.execute(text(query))
                    conn.commit()
                    logger.info(f"✅ Executed on {table}: {query[:50]}...")
                except Exception as e:
                    logger.warning(f"⚠️ Error on {table} for query '{query[:50]}...': {e}")
                    conn.rollback()
    return True

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    from sqlalchemy import create_engine
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set")
    eng = create_engine(db_url)
    logging.basicConfig(level=logging.INFO)
    run(eng)
    logging.info("FTS optimization migration done.")
