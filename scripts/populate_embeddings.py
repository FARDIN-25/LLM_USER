
import sys
import os
import time
from sqlalchemy import text, create_engine
from sentence_transformers import SentenceTransformer

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.shared.config import settings

def populate_embeddings():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(db_url)
    
    # Load Model
    print(">>> Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    tables = ["docs_chunks", "book_chunks"]
    
    for table in tables:
        print(f"\n>>> Processing {table}...")
        
        # 1. Fetch rows without embeddings
        with engine.connect() as conn:
            rows = conn.execute(text(f"SELECT id, chunk_text FROM {table} WHERE embedding IS NULL")).fetchall()
            print(f"Found {len(rows)} rows to process.")
            
            # 2. Update in batches for performance
            count = 0
            for idx, row in enumerate(rows):
                id_val, content = row
                if not content: continue
                
                embedding = model.encode(content).tolist()
                
                # Update row
                conn.execute(
                    text(f"UPDATE {table} SET embedding = :e WHERE id = :id"),
                    {"e": embedding, "id": id_val}
                )
                conn.commit()
                
                count += 1
                if count % 100 == 0:
                    print(f"  Processed {count}/{len(rows)}...")

        print(f"✅ {table} completed. {count} embeddings backfilled.")

if __name__ == "__main__":
    try:
        populate_embeddings()
        print("\n[SUCCESS] Embedding backfill completed.")
    except Exception as e:
        print(f"\n[ERROR] Backfill failed: {e}")
        sys.exit(1)
