
import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chat_service.application.chat_service import ChatService
from src.rag_service.domain.intent_classifier import IntentClassifier
from src.shared import schemas

async def test_production_pipeline():
    print("--- Starting Production Pipeline Verification ---")
    
    # Mock DB and Embedding Model
    mock_db = MagicMock()
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    
    service = ChatService(db=mock_db, embedding_model=mock_model)
    
    # Simulate history: User asked "Who is Bhaaskar?", Assistant replied "CEO"
    history = [
        {"role": "user", "content": "Who is Bhaaskar?"},
        {"role": "assistant", "content": "Bhaaskar is the CEO of Fintax."}
    ]
    
    # 1. Intent Classification Tests (Deterministic)
    test_queries = [
        ("bhaaskar", "ENTITY"),
        ("who is bhaaskar", "DEFINITION"),
        ("tell me about bhaaskar", "GENERAL"),
        ("what about him", "FOLLOW_UP")
    ]
    print("\n[1] Intent Classification:")
    for query, expected in test_queries:
        intent = IntentClassifier.classify(query)
        print(f"'{query}' -> {intent}")
        assert intent == expected

    # 2. Follow-up resolution
    print("\n[2] Follow-up Resolution:")
    from src.followup_service.infrastructure.history_repository import HistoryRepository
    HistoryRepository.get_history_list = MagicMock(return_value=history)
    HistoryRepository.get_history_text = MagicMock(return_value="")
    
    payload = MagicMock()
    payload.get_question_text.return_value = "what about him"
    payload.session_id = "test_session"
    payload.user_id = "test_user"
    payload.is_temporary = False
    payload.category = "GENERAL"
    payload.language = "english"
    payload.query_metadata = {}
    
    def capture_retrieve(original, search, limit, rank, hybrid, intent):
        capture_retrieve.search_query = search
        return []
    service._retrieve_documents = capture_retrieve
    service._generate_answer = MagicMock(return_value={"answer": "Mocked", "tags": []})
    service._save_response = MagicMock(return_value=MagicMock(id="res_123"))
    service._create_chat_message = MagicMock()
    service._ensure_session = MagicMock()
    
    from src.db_service import crud
    crud.create_query = MagicMock(return_value=MagicMock(id="q_123"))
    
    await service.process_chat(payload)
    print(f"Original: 'what about him' -> Retrieval Query: '{capture_retrieve.search_query}'")
    # Per user logic: last_query = history[-1]["content"] which is the Assistant message
    assert capture_retrieve.search_query == history[-1]["content"]
    print("Resolution verified based on provided logic (uses last message content).")

if __name__ == "__main__":
    asyncio.run(test_production_pipeline())
