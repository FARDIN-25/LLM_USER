
import asyncio
import sys
import os
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.db_service.database import SessionLocal
from src.chat_service.application.chat_service import ChatService

async def verify_hybrid():
    db = SessionLocal()
    print(">>> [VERIFY] Connecting to DB...", flush=True)
    
    # Explicitly load model for the service
    print(">>> [VERIFY] Loading model...", flush=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    service = ChatService(db, embedding_model=model)
    
    test_queries = ["What is GST", "define GST"]
    
    for query in test_queries:
        print(f"\n>>> [VERIFY] Testing query: {query}", flush=True)
        try:
            results = await service._retrieve_documents(
                original_query=query,
                search_query=query,
                limit=5,
                reranking_enabled=False,
                hybrid_retrieval_enabled=True,
                intent="GENERAL"
            )
            print(f">>> [VERIFY] Results returned: {len(results)}", flush=True)
            for i, r in enumerate(results):
                print(f"  [{i+1}] {r['text'][:100]}...", flush=True)
        except Exception as e:
            print(f">>> [VERIFY ERROR] {e}", flush=True)
            import traceback
            traceback.print_exc()

    db.close()

if __name__ == "__main__":
    asyncio.run(verify_hybrid())
