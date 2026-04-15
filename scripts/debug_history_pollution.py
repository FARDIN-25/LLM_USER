# scripts/debug_history_pollution.py
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.application.query_rewriter import get_query_rewriter
from src.shared.config import settings

def debug_pollution():
    rewriter = get_query_rewriter()
    
    # Simulate a GST-heavy conversation
    history = [
        {"role": "user", "content": "What is GST?"},
        {"role": "assistant", "content": "GST is a multi-stage tax system in India governed by the GST Act 2017. It replaced multiple indirect taxes like VAT and service tax. It is managed by the CBIC and ICAI."},
        {"role": "user", "content": "Tell me more about ITC"},
        {"role": "assistant", "content": "Input Tax Credit (ITC) allows you to reduce the tax you have already paid on inputs from your tax liability on outputs. It is covered under Section 16 of the GST Act."}
    ]
    
    query = "who is bhaaskar"
    
    print(f"Testing Query: '{query}' with GST history...")
    result = rewriter.rewrite(query, history)
    
    print("\n--- REWRITER OUTPUT ---")
    print(json.dumps(result, indent=2))
    print("-----------------------\n")
    
    if "gst" in str(result.get("retrieval_query")).lower() and result.get("category") == "GENERAL":
        print("⚠️ POLLUTION DETECTED: Retrieval query contains 'gst' but category is 'GENERAL'.")
    elif "gst" in str(result.get("retrieval_query")).lower():
        print("⚠️ BIAS DETECTED: Category is still GST/ITC despite general name.")
    else:
        print("✅ CLEAN: Retrieval query is domain-agnostic.")

if __name__ == "__main__":
    if not settings.OPENROUTER_API_KEY and not settings.MISTRAL_API_KEY:
        print("Error: No API keys found.")
        sys.exit(1)
    
    debug_pollution()
