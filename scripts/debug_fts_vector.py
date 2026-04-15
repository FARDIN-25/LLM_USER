
import sys
import os
from sqlalchemy import text, create_engine
from sentence_transformers import SentenceTransformer

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.shared.config import settings

def debug():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(db_url)
    
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query = "gst"
    emb = model.encode(query).tolist()
    
    with engine.connect() as conn:
        for table in ["docs_chunks", "book_chunks"]:
            print(f"\n>>> DEBUGGING TABLE: {table}")
            
            # FTS Check
            fts_sql = text(f"SELECT count(*) FROM {table} WHERE fts_vector @@ plainto_tsquery('english', :k)")
            fts_cnt = conn.execute(fts_sql, {"k": query}).scalar()
            print(f"  FTS Matches for 'gst': {fts_cnt}")
            
            # Vector Check
            vec_sql = text(f"SELECT count(*) FROM {table} WHERE embedding IS NOT NULL")
            vec_cnt = conn.execute(vec_sql).scalar()
            print(f"  Rows WITH Embeddings: {vec_cnt}")
            
            # Real Vector Search SQL
            vec_s_sql = text(f"SELECT id, 1 - (embedding <=> :e) as score FROM {table} WHERE embedding IS NOT NULL ORDER BY score DESC LIMIT 5")
            res_v = conn.execute(vec_s_sql, {"e": emb}).fetchall()
            print(f"  Top Vector Scores: {[r[1] for r in res_v]}")

if __name__ == "__main__":
    debug()
