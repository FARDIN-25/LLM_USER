import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chat_service.application.chat_service import ChatService

async def test_keyword_extraction_and_fts():
    print("--- Testing Aggressive Keyword Extraction & Strict FTS ---")
    
    mock_db = MagicMock()
    mock_embedding_model = MagicMock()
    
    service = ChatService(db=mock_db)
    service.embedding_model = mock_embedding_model
    
    with patch('src.chat_service.application.chat_service.asyncio.to_thread') as mock_thread:
        # Scenario 1: Keyword Extraction logic
        query_1 = "who is mr.bhaaskar t"
        print(f"\nScenario 1: Keyword Extraction - '{query_1}'")
        
        # We need to simulate the internal extract_keyword indirectly by checking what's passed to thread
        # Mock FTS returning a result
        mock_thread.return_value = [{"id": 1, "text": "Bhaaskar T.S. is the CEO of the company.", "metadata": {}}]
        
        chunks = await service._retrieve_documents(query_1, "expanded", 5, False, True)
        
        # Check if "bhaaskar" was the keyword passed to the first thread call (FTS)
        # Note: In our current implementation, we pass the keyword to _run_search_sync
        actual_keyword = mock_thread.call_args_list[0][0][1]
        print(f"Extracted keyword passed to FTS: '{actual_keyword}'")
        assert actual_keyword == "bhaaskar"
        assert len(chunks) == 1
        assert "bhaaskar" in chunks[0]["text"].lower()

        # Scenario 2: Context Validation
        query_2 = "tell me about mr. unknown"
        print(f"\nScenario 2: Context Validation - '{query_2}'")
        
        # Mock FTS returning irrelevant data
        mock_thread.return_value = [{"id": 2, "text": "GST registration rules for businesses.", "metadata": {}}]
        
        chunks = await service._retrieve_documents(query_2, "expanded", 5, False, True)
        
        print(f"Chunks after validation: {len(chunks)}")
        assert len(chunks) == 0

    print("\n--- All FTS Integration Tests Passed ---")

if __name__ == "__main__":
    asyncio.run(test_keyword_extraction_and_fts())
