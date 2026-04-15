import sys
import os
from sqlalchemy import text, create_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.shared.config import settings

def check_count():
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT count(*) FROM book_chunks WHERE embedding IS NULL")).scalar()
        print(f"Remaining in book_chunks: {cnt}")

if __name__ == "__main__":
    check_count()
