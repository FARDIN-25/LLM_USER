"""
Migration: Rename file_uploads.folder_assignment to file_uploads.tags.
Safe to run multiple times (skips if already renamed).
"""
import logging
from sqlalchemy import text

logger = logging.getLogger("fintax")


def run_rename_file_uploads_folder_assignment_to_tags(engine):
    """Rename column folder_assignment to tags in file_uploads if it exists."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'file_uploads'
                    AND column_name = 'folder_assignment'
                )
            """)
        )
        has_folder_assignment = result.scalar()
        if not has_folder_assignment:
            logger.info("✅ file_uploads.folder_assignment already renamed or absent, skipping")
            conn.commit()
            return True
        conn.execute(text("ALTER TABLE file_uploads RENAME COLUMN folder_assignment TO tags"))
        conn.commit()
        logger.info("✅ Renamed file_uploads.folder_assignment to file_uploads.tags")
    return True
