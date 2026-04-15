import sys
import os

# Ensure the app can find the src module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import text
from src.db_service.database import engine

print("Connecting to database...")
try:
    with engine.begin() as conn:
        print("Executing ALTER TABLE command...")
        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN session_metadata JSON NULL;"))
        print("✅ Successfully added session_metadata column to chat_sessions table!")
except Exception as e:
    print(f"❌ Error (column might already exist): {e}")

