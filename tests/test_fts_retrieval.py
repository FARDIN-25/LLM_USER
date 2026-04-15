import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db_service.database import SessionLocal
from src.vector_service.infrastructure.search_logic import sparse_search_postgres, hybrid_retrieve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_fts")

def test_retrieval():
    db = SessionLocal()
    try:
        query = "tax"  # Use a keyword likely to be in the dataset
        logger.info(f"Testing multi-table sparse search for query: '{query}'")
        
        sparse_results = sparse_search_postgres(db, query, k=3)
        logger.info(f"Sparse results count: {len(sparse_results)}")
        for i, res in enumerate(sparse_results):
            meta = res['doc']['metadata']
            logger.info(f"  {i+1}. Source: {meta.get('source_file')}, Domain: {meta.get('domain')}, Score: {res['score']:.4f}, Text: {res['doc']['text'][:100]}...")

        if not sparse_results:
             logger.warning("No sparse results found. Verify that 'docs_chunks' or 'books_chunks' have data and fts_vector is populated.")

        logger.info("Testing hybrid retrieval...")
        # Mock embedding (zeros)
        mock_embedding = [0.0] * 384
        hybrid_results = hybrid_retrieve(db, query, mock_embedding, k=3)
        logger.info(f"Hybrid results count: {len(hybrid_results)}")
        for i, res in enumerate(hybrid_results):
            meta = res['doc']['metadata']
            logger.info(f"  {i+1}. Source: {meta.get('source_file')}, Type: {res['type']}, Score: {res['score']:.4f}")

        logger.info("Verification tests completed!")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    test_retrieval()
