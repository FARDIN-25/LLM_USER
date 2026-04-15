"""
Migration: create chat_sessions, chat_messages, subscriptions, file_uploads, message_reactions if they do not exist.
Safe to run multiple times (checkfirst=True).
"""
import logging
from sqlalchemy import text

logger = logging.getLogger("fintax")


def run_tables_migration(engine):
    """Create chat_sessions, user_queries, query_responses, chat_messages, subscriptions, file_uploads if missing.
    Order matters: ChatSession first (UserQuery FK), then UserQuery, then QueryResponse (ChatMessage FKs)."""
    from src.db_service.database import Base
    from .. import models

    # Dependency order: chat_sessions -> user_queries -> query_responses -> chat_messages
    table_models = [
        models.ChatSession,
        models.Subscription,
        models.FileUpload,
        models.UserQuery,
        models.QueryResponse,
        models.ChatMessage,
    ]
    
    created_count = 0
    failed_count = 0
    
    for model in table_models:
        try:
            model.__table__.create(bind=engine, checkfirst=True)
            logger.info("✅ Table ready: %s", model.__tablename__)
            created_count += 1
        except Exception as e:
            logger.error("❌ Failed to create table %s: %s", model.__tablename__, e, exc_info=True)
            failed_count += 1
    
    if failed_count > 0:
        logger.warning("⚠️ Migration completed with %d failures out of %d tables", failed_count, len(table_models))
    else:
        logger.info("✅ All %d tables migrated successfully", created_count)
    
    # Verify critical tables exist
    try:
        with engine.connect() as conn:
            for model in table_models:
                result = conn.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_name = :table_name
                        )
                    """),
                    {"table_name": model.__tablename__}
                )
                exists = result.scalar()
                if exists:
                    logger.debug("✅ Verified table exists: %s", model.__tablename__)
                else:
                    logger.error("❌ Table verification failed: %s does not exist", model.__tablename__)
    except Exception as e:
        logger.warning("⚠️ Table verification skipped: %s", e)
    
    return True
