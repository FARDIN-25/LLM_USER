"""
Migration: add indexes on session_id, user_id, react for performance.
Run once after deploying models. Uses IF NOT EXISTS so safe to re-run.
Usage: from src.db_service.database import engine; from src.db_service.migrations.add_indexes import run; run(engine)
"""
import logging
from sqlalchemy import text

logger = logging.getLogger("fintax")

INDEXES = [
    # chat_sessions
    ("chat_sessions", "ix_chat_sessions_user_id", "CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id ON chat_sessions (user_id)"),
    ("chat_sessions", "ix_chat_sessions_session_id", "CREATE INDEX IF NOT EXISTS ix_chat_sessions_session_id ON chat_sessions (session_id)"),
    # chat_messages
    ("chat_messages", "ix_chat_messages_session_id", "CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages (session_id)"),
    ("chat_messages", "ix_chat_messages_react", "CREATE INDEX IF NOT EXISTS ix_chat_messages_react ON chat_messages (react)"),
    ("chat_messages", "ix_chat_messages_query_id", "CREATE INDEX IF NOT EXISTS ix_chat_messages_query_id ON chat_messages (query_id)"),
    ("chat_messages", "ix_chat_messages_response_id", "CREATE INDEX IF NOT EXISTS ix_chat_messages_response_id ON chat_messages (response_id)"),
    # user_queries
    ("user_queries", "ix_user_queries_session_id", "CREATE INDEX IF NOT EXISTS ix_user_queries_session_id ON user_queries (session_id)"),
    ("user_queries", "ix_user_queries_user_id", "CREATE INDEX IF NOT EXISTS ix_user_queries_user_id ON user_queries (user_id)"),
    # file_uploads
    ("file_uploads", "ix_file_uploads_user_id", "CREATE INDEX IF NOT EXISTS ix_file_uploads_user_id ON file_uploads (user_id)"),
    ("file_uploads", "ix_file_uploads_session_id", "CREATE INDEX IF NOT EXISTS ix_file_uploads_session_id ON file_uploads (session_id)"),
    ("file_uploads", "ix_file_uploads_tags", "CREATE INDEX IF NOT EXISTS ix_file_uploads_tags ON file_uploads (tags)"),
    # subscriptions
    ("subscriptions", "ix_subscriptions_user_id", "CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions (user_id)"),
    # document_chunks (folder_assignment already in model)
    ("document_chunks", "ix_document_chunks_folder_assignment", "CREATE INDEX IF NOT EXISTS ix_document_chunks_folder_assignment ON document_chunks (folder_assignment)"),
]


def run(engine):
    """Apply indexes. Safe to run multiple times."""
    with engine.connect() as conn:
        for table, name, sql in INDEXES:
            try:
                conn.execute(text(sql))
                conn.commit()
                logger.info("Index created/verified: %s on %s", name, table)
            except Exception as e:
                logger.warning("Index %s: %s", name, e)
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
    logging.info("Indexes migration done.")
