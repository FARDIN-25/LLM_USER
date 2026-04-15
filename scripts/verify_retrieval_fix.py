# scripts/verify_retrieval_fix.py
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chat_service.application.chat_service import ChatService

async def test_retrieval():
    db = MagicMock()
    service = ChatService(db)
    
    # Mocking external calls
    with patch('src.rag_service.domain.keyword_extractor.KeywordExtractor.extract') as mock_extract:
        mock_extract.return_value = "GST"
        
        print("Testing _retrieve_documents...")
        try:
            # This should now run without NameError
            chunks = await service._retrieve_documents(
                original_query="What is GST?",
                search_query="What is GST?",
                limit=5,
                reranking_enabled=False,
                hybrid_enabled=False
            )
            print("✅ _retrieve_documents ran successfully!")
            print(f"Extracted keyword logic worked. Result chunks: {len(chunks)}")
        except Exception as e:
            print(f"❌ Error in _retrieve_documents: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_retrieval())
