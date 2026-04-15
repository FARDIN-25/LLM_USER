# scripts/verify_final_fix.py
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.application.query_rewriter import get_query_rewriter
from src.shared.config import settings

def test_final_fix():
    rewriter = get_query_rewriter()
    
    test_cases = [
        {
            "name": "General Identity (Suguna)",
            "query": "who is suguna",
            "history": []
        },
        {
            "name": "General Identity (Bhaaskar)",
            "query": "what is bhaaskar",
            "history": []
        },
        {
            "name": "GST Specific (ITC Types)",
            "query": "define the types",
            "history": [{"role": "user", "content": "What is ITC?"}]
        }
    ]
    
    print(f"{'Test Case':<25} | {'Category':<10} | {'Rewritten Query':<35}")
    print("-" * 80)
    
    for case in test_cases:
        result = rewriter.rewrite(case["query"], case["history"])
        
        if isinstance(result, dict):
            print(f"{case['name']:<25} | {result.get('category'):<10} | {result.get('rewritten_query')[:35]}")
            print(f"  -> Retrieval Query: {result.get('retrieval_query')}")
        else:
            print(f"{case['name']:<25} | {'STRING':<10} | {result[:35]}")
        print("-" * 80)

if __name__ == "__main__":
    if not settings.OPENROUTER_API_KEY and not settings.MISTRAL_API_KEY:
        print("Error: No API keys found.")
        sys.exit(1)
        
    try:
        test_final_fix()
        print("\n✅ Verification complete.")
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
