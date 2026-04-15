"""
Migration: add 'category' column to user_queries for automatic topic clustering.

- No new tables
- Safe to run multiple times (uses IF NOT EXISTS / error-tolerant pattern)

Usage (one-off):

    from src.db_service.database import engine
    from src.db_service.migrations.add_user_query_category import run
    run(engine)
"""
import logging
from sqlalchemy import text

logger = logging.getLogger("fintax")


SQL_ADD_COLUMN = """
ALTER TABLE IF EXISTS user_queries
ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'GENERAL';
"""

SQL_ADD_INDEX = """
CREATE INDEX IF NOT EXISTS ix_user_queries_category
ON user_queries (category);
"""


def run(engine):
    """Apply 'category' column + index for user_queries. Safe to call multiple times."""
    with engine.connect() as conn:
        try:
            conn.execute(text(SQL_ADD_COLUMN))
            conn.commit()
            logger.info("Column user_queries.category created/verified.")
        except Exception as e:
            logger.warning("Category column migration: %s", e)
            conn.rollback()

        try:
            conn.execute(text(SQL_ADD_INDEX))
            conn.commit()
            logger.info("Index ix_user_queries_category created/verified.")
        except Exception as e:
            logger.warning("Category index migration: %s", e)
            conn.rollback()

    return True


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    logging.basicConfig(level=logging.INFO)
    load_dotenv()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set")

    eng = create_engine(db_url)
    run(eng)
    logger.info("user_queries.category migration done.")

