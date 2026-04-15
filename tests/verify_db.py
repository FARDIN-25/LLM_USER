import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db_service.database import SessionLocal

def verify_db():
    db = SessionLocal()
    try:
        print("--- Database Verification ---")
        
        # Check docs_chunks
        docs_count = db.execute(text("SELECT count(*) FROM docs_chunks")).scalar()
        docs_fts = db.execute(text("SELECT count(*) FROM docs_chunks WHERE fts_vector IS NOT NULL")).scalar()
        print(f"Docs Chunks: {docs_count} total, {docs_fts} with FTS vector")
        
        # Check book_chunks
        books_count = db.execute(text("SELECT count(*) FROM book_chunks")).scalar()
        books_fts = db.execute(text("SELECT count(*) FROM book_chunks WHERE fts_vector IS NOT NULL")).scalar()
        print(f"Books Chunks: {books_count} total, {books_fts} with FTS vector")
        
        # Check responses
        resp_count = db.execute(text("SELECT count(*) FROM query_responses")).scalar()
        print(f"Total Responses Generated: {resp_count}")
        
        if resp_count > 0:
            last_resp = db.execute(text("SELECT response_text, created_at FROM query_responses ORDER BY created_at DESC LIMIT 1")).fetchone()
            print(f"Last Response (at {last_resp[1]}):")
            print(f"{last_resp[0][:200]}...")
            
        print("--- End Verification ---")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_db()
