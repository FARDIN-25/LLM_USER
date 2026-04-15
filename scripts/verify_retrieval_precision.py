
import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chat_service.application.chat_service import ChatService
from src.shared import schemas

async def test_retrieval_precision():
    print("--- Starting Retrieval Precision Verification ---")
    
    # Mock DB and Embedding Model
    mock_db = MagicMock()
    mock_model = MagicMock()
    mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)
    
    service = ChatService(db=mock_db, embedding_model=mock_model)
    
    # Mock data
    mock_chunks = [
        {"id": 1, "text": "Bhaaskar is the CEO of Fintax.", "score": 0.9},
        {"id": 2, "text": "Taxation in India is complex.", "score": 0.5},
        {"id": 3, "text": "The Goods and Services Tax was introduced in 2017.", "score": 0.4},
        {"id": 4, "text": "Who is Bhaaskar? He leads the technology team.", "score": 0.8}
    ]

    # 1. Test Stage 1: FTS results found
    print("\n[1] Testing FTS Priority and Filtering:")
    
    # Mock _run_fts_search (internal to _retrieve_documents refactor, so we mock the flow)
    # Actually, we can just mock the whole methods used in the thread
    
    def mock_fts(q):
        return mock_chunks # Return all, filtering should remove unrelated ones
    
    # In my refactor, _run_fts_search is a local function. 
    # To test it, we can run the real method but mock the DB execute.
    
    from sqlalchemy.engine import Row
    def mock_execute(stmt, params):
        # Simulate FTS result for "bhaaskar"
        if "bhaaskar" in params.get("k", "").lower():
            # Return rows 1 and 4
            results = [
                MagicMock(id=1, content="Bhaaskar is the CEO of Fintax.", metadata={}, rank=0.9),
                MagicMock(id=4, content="Who is Bhaaskar? He leads the technology team.", metadata={}, rank=0.8),
                MagicMock(id=2, content="Taxation in India is complex.", metadata={}, rank=0.1)
            ]
            return MagicMock(fetchall=lambda: results)
        return MagicMock(fetchall=lambda: [])

    # Mock SessionLocal and DB
    mock_session = MagicMock()
    mock_session.execute = mock_execute
    with MagicMock() as mock_db_ctx:
        from src.db_service.database import SessionLocal
        import src.chat_service.application.chat_service as cs_mod
        
        # We need to monkeypatch SessionLocal inside the method scope
        # Or just test the logic via the service method
        
        service._retrieve_documents_orig = service._retrieve_documents
        
        # We need to simulate the async call
        res = await service._retrieve_documents(
            original_query="who is bhaaskar",
            search_query="bhaaskar",
            limit=5,
            reranking_enabled=False,
            hybrid_enabled=False
        )
        
        print(f"Query: 'bhaaskar' -> Results Count: {len(res)}")
        for i, doc in enumerate(res):
            print(f" Result {i+1}: {doc['text']}")
            assert "bhaaskar" in doc["text"].lower()
        
        assert len(res) <= 3
        print("Success: Retrieval filtered unrelated chunks and respected limit.")

if __name__ == "__main__":
    # Note: Running this requires the actual DB and model setup or very clever mocking.
    # Since I can't easily mock the local function closure without refactoring the code itself,
    # I'll rely on a simpler verification of the code structure and a check of the log.
    print("Verification script created. Running simplified check...")
    asyncio.run(test_retrieval_precision())
