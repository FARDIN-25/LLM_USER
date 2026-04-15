
import sys
import os
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.application.query_rewriter import QueryRewriter
from src.rag_service.infrastructure.prompt_templates import detect_template_from_question

def test_query(query, history=[]):
    results = []
    results.append(f"\n--- Testing Query: '{query}' ---")
    
    # Test Template Detection
    template_id, extra_params = detect_template_from_question(query)
    results.append(f"Detected Template: {template_id}")
    results.append(f"Extra Params: {extra_params}")
    
    # Test Query Rewriting
    rewriter = QueryRewriter()
    # We'll monkey-patch logger to see what happens
    import logging
    logger = logging.getLogger("fintax")
    
    result = rewriter.rewrite(query, history)
    results.append(f"Rewritten Query: {result.get('rewritten_query')}")
    results.append(f"Retrieval Query: {result.get('retrieval_query')}")
    results.append(f"Keywords: {result.get('keywords')}")
    results.append(f"Category: {result.get('category')}")
    return "\n".join(results)

if __name__ == "__main__":
    output = []
    output.append(test_query("GST who is bhaaskar"))
    output.append(test_query("who is bhaaskar"))
    
    with open("repro_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    print("Results written to repro_results.txt")
