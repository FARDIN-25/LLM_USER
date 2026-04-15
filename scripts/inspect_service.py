
import asyncio
import sys
import os
import inspect
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.db_service.database import SessionLocal
from src.chat_service.application.chat_service import ChatService

async def inspect_service():
    db = SessionLocal()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    service = ChatService(db, embedding_model=model)
    
    print(">>> INSPECTING _retrieve_documents:")
    try:
        source = inspect.getsource(service._retrieve_documents)
        print(source)
    except Exception as e:
        print(f"FAILED TO GET SOURCE: {e}")

    db.close()

if __name__ == "__main__":
    asyncio.run(inspect_service())
