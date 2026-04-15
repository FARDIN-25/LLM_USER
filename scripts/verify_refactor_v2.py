
import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chat_service.application.chat_service import ChatService
from src.rag_service.domain.intent_classifier import IntentClassifier
from src.shared import schemas

async def test_pipeline():
    print("--- Starting Pipeline Verification (v2) ---")
    
    # Mock DB and Embedding Model
    mock_db = MagicMock()
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    
    service = ChatService(db=mock_db, embedding_model=mock_model)
    
    # Test cases
    test_queries = [
        ("bhaaskar", "ENTITY"),
        ("who is bhaaskar", "DEFINITION"),
        ("tell me about bhaaskar", "GENERAL"),
        ("what about him", "FOLLOW_UP")
    ]
    
    # Simulate history for "what about him"
    history = [
        {"role": "user", "content": "who is bhaaskar"},
        {"role": "assistant", "content": "Bhaaskar is the CEO of Fintax."}
    ]
    
    # 1. Test Intent Classification directly
    print("\n[1] Intent Classification Tests:")
    for query, expected in test_queries:
        intent = IntentClassifier.classify(query)
        print(f"Query: '{query}' -> Intent: {intent} (Expected: {expected})")
        assert intent == expected, f"Failed for {query}"

    # 2. Test Follow-up resolution in ChatService
    print("\n[2] Follow-up Resolution Test:")
    # Mock HistoryRepository.get_history_list to return our simulated history
    from src.followup_service.infrastructure.history_repository import HistoryRepository
    HistoryRepository.get_history_list = MagicMock(return_value=history)
    HistoryRepository.get_history_text = MagicMock(return_value="")
    
    # Use a real schema.QueryCreate but mock get_question_text for simplicity
    payload = MagicMock()
    payload.get_question_text.return_value = "what about him"
    payload.session_id = "test_session"
    payload.user_id = "test_user"
    payload.is_temporary = False
    payload.category = "GENERAL"
    payload.language = "english"
    payload.query_metadata = {}
    
    # Capture the search_query passed to _retrieve_documents
    def capture_retrieve(original, search, limit, rank, hybrid, intent):
        capture_retrieve.search_query = search
        return []
    service._retrieve_documents = capture_retrieve
    
    service._generate_answer = MagicMock(return_value={"answer": "Mocked", "tags": []})
    service._save_response = MagicMock(return_value=MagicMock(id="res_123"))
    service._create_chat_message = MagicMock()
    service._ensure_session = MagicMock()
    
    # Mock crud.create_query
    from src.db_service import crud
    crud.create_query = MagicMock(return_value=MagicMock(id="q_123"))
    
    res = await service.process_chat(payload)
    print(f"\n[3] Final Retrieval Query check:")
    print(f"Original: 'what about him' -> Retrieval Query: '{capture_retrieve.search_query}'")
    assert capture_retrieve.search_query == "who is bhaaskar"
    print("Assertion passed: Follow-up correctly resolved to last user query.")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
