
import sys
import os
from sqlalchemy import text, create_engine

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.shared.config import settings

def apply_automation():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(db_url)
    
    # Read the SQL file
    sql_path = os.path.join(os.path.dirname(__file__), 'setup_fts_triggers.sql')
    with open(sql_path, 'r') as f:
        # Split by empty lines or some delimiter if needed, 
        # but for triggers we can run the whole block
        sql_script = f.read()

    print(">>> APPLYING AUTOMATED FTS TRIGGERS...")
    with engine.connect() as conn:
        with conn.begin():
            # We run it as one block. Postgres handles multiple statements in some drivers, 
            # but let's be safe and split by ';' if it fails, or just wrap in DO block.
            # Actually, most psycopg2 connections handle this fine.
            conn.execute(text(sql_script))
    
    print("✅ Automation applied successfully. Your tables are now self-indexing!")

if __name__ == "__main__":
    apply_automation()
