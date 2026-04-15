import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.db_service.database import SessionLocal
from src.db_service import crud

session_id = "01042026-24a09f17"

test_metadata = {
  "profile": {
    "name": "Arun Kumar",
    "pan": "ABCDE1234F"
  },
  "financials": {
    "income_sources": ["salary", "freelance"],
    "tax_regime": "old"
  },
  "notices": {
    "active_notices": [{"type": "Defective Return", "section": "139(9)"}]
  }
}

print(f"Injecting test metadata into Session ID: {session_id} ...")

db = SessionLocal()
try:
    updated_session = crud.update_session_metadata(db, session_id, test_metadata)
    if updated_session:
        print("✅ SUCCESS! The metadata was successfully injected into the database.")
        print("Current saved metadata:")
        print(updated_session.session_metadata)
    else:
        print("❌ FAILED. Could not find a ChatSession with that ID in the database.")
finally:
    db.close()
