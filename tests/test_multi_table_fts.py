import sys
import os
import asyncio
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import ProgrammingError

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chat_service.application.chat_service import ChatService

async def test_multi_table_fts_tolerance():
    print("--- Testing Multi-Table FTS Fault Tolerance ---")
    
    mock_db = MagicMock()
    # Mock execute to simulate failure on 'docs_chunks' but success on 'book_chunks'
    def mock_execute(stmt, params):
        stmt_str = str(stmt).lower()
        if "from docs_chunks" in stmt_str:
            raise ProgrammingError("SELECT", {}, "Column 'fts_vector' does not exist")
        
        # Simulate 'book_chunks' success
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(id=101, content="Book entry about Bhaaskar", metadata={}, rank=0.8)
        ]
        return mock_result

    mock_db.execute.side_effect = mock_execute
    
    # We need to mock SessionLocal which is imported inside the function
    with patch('src.db_service.database.SessionLocal', return_value=mock_db):
        service = ChatService(db=mock_db)
        # Mock embedding model to avoid initialization error though it shouldn't be reached
        service.embedding_model = MagicMock()
        
        # Call _retrieve_documents
        print("Calling _retrieve_documents with 'who is bhaaskar'...")
        results = await service._retrieve_documents("who is bhaaskar", "expanded", 5, False, True)
        
        print(f"Final combined results count: {len(results)}")
        assert len(results) > 0
        assert results[0]["id"] == 101
        assert "Book entry" in results[0]["text"]
        
        print("Successfully retrieved results from book_chunks despite docs_chunks failure!")

    print("\n--- Multi-Table FTS Tests Passed ---")

if __name__ == "__main__":
    asyncio.run(test_multi_table_fts_tolerance())
