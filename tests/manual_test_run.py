import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, patch
from src.vector_service.infrastructure.search_logic import (
    dense_search_pgvector,
    hybrid_retrieve,
    SearchDoc,
    SearchResult
)

def run_tests():
    print("Running manual tests...")
    
    # Mock data
    mock_documents = [
        {"id": 1, "content": "Apple is a fruit", "metadata": {"category": "fruit"}},
        {"id": 2, "content": "Banana is yellow", "metadata": {"category": "fruit"}},
        {"id": 3, "content": "Carrot is a vegetable", "metadata": {"category": "vegetable"}},
    ]
    
    # Test BM25 (Deprecated: sparse_search_postgres uses DB, so mocked here)
    print("Skipping in-memory BM25 test...")
    
    # Test Dense
    print("Testing Dense...")
    mock_db = MagicMock()
    mock_row = MagicMock()
    mock_row.id = 1
    mock_row.chunk_text = "Dense result text"
    mock_row.chunk_metadata = {"source": "test"}
    mock_row.score = 0.85
    mock_row.source = "docs"
    mock_db.execute.return_value.fetchall.return_value = [mock_row]
    
    results = dense_search_pgvector(mock_db, [0.1]*384, k=1)
    assert len(results) == 1
    assert results[0]["doc"]["id"] == "docs_1"
    print("Dense OK")

    # Test Hybrid
    print("Testing Hybrid...")
    with patch("src.vector_service.infrastructure.search_logic.dense_search_pgvector") as mock_dense:
        mock_dense.return_value = [
            {"doc": {"id": 1, "content": "doc1", "metadata": {}}, "score": 0.9, "type": "dense"},
            {"doc": {"id": 2, "content": "doc2", "metadata": {}}, "score": 0.5, "type": "dense"}
        ]
        
        with patch("src.vector_service.infrastructure.search_logic.sparse_search_postgres") as mock_sparse:
            mock_sparse.return_value = [
                {"doc": {"id": "docs_1", "content": "doc1", "metadata": {}}, "score": 0.9, "type": "sparse"},
                {"doc": {"id": "book_3", "content": "doc3", "metadata": {}}, "score": 0.5, "type": "sparse"}
            ]
            
            results = hybrid_retrieve(
                db=mock_db,
                query="test",
                query_embedding=[0.1]*384,
                k=3
            )
            
            ids = [r["doc"]["id"] for r in results]
            print(f"Hybrid Results IDs: {ids}")
            assert "docs_1" in ids
            print("Hybrid OK")

if __name__ == "__main__":
    try:
        run_tests()
        print("All manual tests passed!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
