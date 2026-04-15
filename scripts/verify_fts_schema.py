from src.db_service.database import SessionLocal
from sqlalchemy import text

def verify_schema():
    db = SessionLocal()
    try:
        tables = ["docs_chunks", "book_chunks"]
        for table in tables:
            print(f"Checking table: {table}")
            
            # Check if column exists
            res = db.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' AND column_name = 'fts_vector'
            """)).fetchone()
            
            if not res:
                print(f"Adding fts_vector to {table}...")
                db.execute(text(f"ALTER TABLE {table} ADD COLUMN fts_vector tsvector"))
                db.execute(text(f"UPDATE {table} SET fts_vector = to_tsvector('english', chunk_text)"))
                db.execute(text(f"CREATE INDEX idx_{table}_fts ON {table} USING GIN(fts_vector)"))
                db.commit()
                print(f"fts_vector added to {table}")
            else:
                print(f"fts_vector already exists in {table}")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    verify_schema()
