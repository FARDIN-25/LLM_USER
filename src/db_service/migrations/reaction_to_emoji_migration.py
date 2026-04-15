"""
Migration: Replace like/unlike and message_reactions with single emoji in chat_messages.react.
- Drops table message_reactions if it exists.
- Alters chat_messages.react from boolean to VARCHAR(20) with default 'no_react'.

Standalone SQL snippet (for manual runs if needed):
  DROP TABLE IF EXISTS message_reactions CASCADE;
  ALTER TABLE chat_messages
    ALTER COLUMN react TYPE VARCHAR(20)
    USING (CASE WHEN react = true THEN 'no_react' ELSE 'no_react' END),
    ALTER COLUMN react SET DEFAULT 'no_react';
"""
import logging
from sqlalchemy import text

logger = logging.getLogger("fintax")


def run_reaction_to_emoji_migration(engine):
    """
    Drop message_reactions table; alter chat_messages.react to string default 'no_react'.
    """
    with engine.connect() as conn:
        # 1. Drop message_reactions table if it exists
        conn.execute(
            text("""
                DROP TABLE IF EXISTS message_reactions CASCADE
            """)
        )
        conn.commit()
        logger.info("✅ Dropped message_reactions table if it existed")

        # 2. Check current type of chat_messages.react
        result = conn.execute(
            text("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'chat_messages' AND column_name = 'react'
            """)
        )
        row = result.fetchone()
        if not row:
            logger.warning("⚠️ chat_messages.react column not found; skipping alter")
            return True
        current_type = (row[0] or "").lower()

        if current_type in ("character varying", "varchar"):
            logger.info("✅ chat_messages.react already VARCHAR, skipping alter")
            return True

        # 3. Alter react from boolean to VARCHAR(20), default 'no_react'
        # Convert: true -> 'no_react', false -> 'no_react' (no preserved "like" state)
        conn.execute(
            text("""
                ALTER TABLE chat_messages
                ALTER COLUMN react TYPE VARCHAR(20)
                USING (CASE WHEN react = true THEN 'no_react' ELSE 'no_react' END),
                ALTER COLUMN react SET DEFAULT 'no_react'
            """)
        )
        conn.commit()
        logger.info("✅ chat_messages.react altered to VARCHAR(20) default 'no_react'")
    return True
