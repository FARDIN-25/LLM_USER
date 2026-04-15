# src/db_service/migrations/inspect_schema.py
import logging
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from sqlalchemy import text
from src.db_service.database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inspect_schema")

def inspect():
    db = SessionLocal()
    tables = ["docs_chunks", "book_chunks", "document_chunks"]
    
    for table in tables:
        try:
            logger.info(f"\n--- Checking Table: {table} ---")
            # List columns
            res = db.execute(text(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
            """)).fetchall()
            
            if not res:
                logger.warning(f"Table {table} not found or no columns.")
                continue
                
            for col in res:
                logger.info(f"  {col.column_name}: {col.data_type}")
                
            # Check indexes
            idx_res = db.execute(text(f"""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = '{table}'
            """)).fetchall()
            logger.info(f"  Indexes:")
            for idx in idx_res:
                logger.info(f"    {idx.indexname}: {idx.indexdef}")
                
        except Exception as e:
            logger.error(f"Error inspecting {table}: {e}")
            
    db.close()

if __name__ == "__main__":
    inspect()
