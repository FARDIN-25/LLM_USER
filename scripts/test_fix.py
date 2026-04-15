import asyncio
import logging
import sys
import os

# Ensure the parent directory is in the path so we can import src
sys.path.append(os.getcwd())

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.shared.config import settings
from src.db_service.database import SessionLocal
from src.chat_service.application.chat_service import ChatService
from src.shared import schemas
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_fix")

async def test():
    db = SessionLocal()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    service = ChatService(db, embedding_model=model)
    
    TEST_QUERIES = [
        "what is GST",
        "types",
        "explain more",
        "eligibility",
        "who is bhaaskar",
        "tell me about him",
        "what is the input tax credit",
        "conditions for it"
    ]
    
    with open("scripts/final_verified_results.txt", "w", encoding="utf-8") as f:
        for q in TEST_QUERIES:
            f.write(f"\n>>> TESTING QUERY: {q}\n")
            payload = schemas.QueryCreate(
                user_id="test_user",
                question=q,
                session_id="test_session",
                is_temporary=True
            )
            try:
                # Get the retrieved documents first to see what's being passed
                retrieved_chunks = await service._retrieve_documents(
                    original_query=q, 
                    search_query=q, 
                    limit=5, 
                    reranking_enabled=True,
                    hybrid_retrieval_enabled=True
                )
                context_str = service._build_context(retrieved_chunks)
                f.write(f"CONTEXT LENGTH: {len(context_str)}\n")
                f.write(f"CONTEXT PREVIEW: {context_str[:500]}...\n")
                
                result = await service.process_chat(payload, hybrid_retrieval_enabled=True)
                f.write(f"REWRITTEN QUERY: {result.get('rewritten_query', 'N/A')}\n")
                f.write(f"SUCCESS: {result['answer']}\n")
            except Exception as e:
                f.write(f"FAILED: {e}\n")
            finally:
                db.rollback()
            
    db.close()

if __name__ == "__main__":
    asyncio.run(test())
