
import sys
import os
from sqlalchemy import text, create_engine

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.shared.config import settings

def check():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print(">>> 1. Checking Extension:")
        res = conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).fetchall()
        print(f"  Vector Extension: {'Enabled' if res else 'MISSING'}")
        
        print("\n>>> 2. Checking Columns:")
        res = conn.execute(text("SELECT table_name, column_name FROM information_schema.columns WHERE column_name = 'embedding'")).fetchall()
        for r in res:
            print(f"  {r[0]}.{r[1]}")
            
        print("\n>>> 3. Detailed Data Audit:")
        for table in ["docs_chunks", "book_chunks"]:
            total = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            clean = conn.execute(text(f"SELECT count(*) FROM {table} WHERE is_clean IS TRUE")).scalar()
            null_clean = conn.execute(text(f"SELECT count(*) FROM {table} WHERE is_clean IS NULL")).scalar()
            has_emb = conn.execute(text(f"SELECT count(*) FROM {table} WHERE embedding IS NOT NULL")).scalar()
            
            print(f"  [{table}]: Total={total}, is_clean=True:{clean}, is_clean=NULL:{null_clean}, with_emb:{has_emb}")

if __name__ == "__main__":
    check()
