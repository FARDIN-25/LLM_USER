
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.application.query_rewriter import QueryRewriter

def test_isolation():
    print("--- Testing Context Isolation: GST History -> 'who is bhaaskar' ---")
    history = [
        {"role": "user", "content": "What is the GST rate for services?"},
        {"role": "assistant", "content": "The GST rate for services is generally 18%..."}
    ]
    query = "who is bhaaskar"
    
    rewriter = QueryRewriter()
    result = rewriter.rewrite(query, history)
    
    print(f"Rewritten: {result.get('rewritten_query')}")
    print(f"Category: {result.get('category')}")
    print(f"Retrieval Query: {result.get('retrieval_query')}")
    
    # Assert isolation
    assert result.get('category') == 'GENERAL'
    assert "GST" not in result.get('retrieval_query')
    print("✅ Context Isolation Verified!")

if __name__ == "__main__":
    test_isolation()
