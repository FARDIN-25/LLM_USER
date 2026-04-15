"""
Migration: Add history JSONB column to chat_sessions.
Stores: { "title": "Short generated title", "first_question": "User first message" }
Safe to run multiple times (IF NOT EXISTS / check before add).
"""
import logging
from sqlalchemy import text

logger = logging.getLogger("fintax")


def run_add_history_column(engine):
    """Add history JSONB column to chat_sessions if it does not exist."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'chat_sessions'
                    AND column_name = 'history'
                )
            """)
        )
        exists = result.scalar()
        if exists:
            logger.info("✅ chat_sessions.history column already exists, skipping")
            conn.commit()
            return True
        conn.execute(
            text("""
                ALTER TABLE chat_sessions
                ADD COLUMN history JSONB DEFAULT '{}'::jsonb
            """)
        )
        conn.commit()
        logger.info("✅ Added chat_sessions.history JSONB column")
    return True
