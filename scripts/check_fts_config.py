from src.db_service.database import SessionLocal
from sqlalchemy import text

def check_fts_config():
    db = SessionLocal()
    try:
        tables = ["docs_chunks", "book_chunks"]
        for table in tables:
            print(f"--- Table: {table} ---")
            # Check for GIN indexes
            index_res = db.execute(text(f"""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = '{table}' AND indexdef LIKE '%USING gin%'
            """)).fetchall()
            print(f"GIN Indexes: {len(index_res)}")
            for idx in index_res:
                print(f"  {idx.indexname}: {idx.indexdef}")
            
            # Check a sample tsvector to see if it looks stemmed or not
            sample = db.execute(text(f"SELECT fts_vector FROM {table} WHERE fts_vector IS NOT NULL LIMIT 1")).fetchone()
            if sample:
                print(f"Sample tsvector: {sample[0]}")
            else:
                print("No tsvector data found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_fts_config()
