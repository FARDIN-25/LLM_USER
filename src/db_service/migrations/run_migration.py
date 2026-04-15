# src/db_service/migrations/run_migration.py
import logging
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from sqlalchemy import text
from src.db_service.database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_migration")

def run(sql_file: str):
    db = SessionLocal()
    try:
        with open(sql_file, "r") as f:
            sql = f.read()
        
        # Split by semicolon for individual execution if needed, 
        # but SQLAlchemy text() can handle multiple statements if supported by driver
        logger.info(f"Executing migration from {sql_file}...")
        
        # PostgreSQL allows multiple statements in one execute() call with text()
        db.execute(text(sql))
        db.commit()
        logger.info("✅ Migration executed successfully.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Migration failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "src/db_service/migrations/rag_standardization.sql"
    run(file_path)
