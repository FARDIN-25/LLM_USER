# scripts/verify_keyword_extraction.py
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.domain.keyword_extractor import KeywordExtractor

async def test_extraction():
    scenarios = [
        {"input": "what is gst", "expected": "GST"},
        {"input": "explain input tax credit", "expected": "input tax credit"},
        {"input": "tell me about gst returns", "expected": "GST returns"},
        {"input": "who is the director of the company", "expected": "director"}, # Domain preference
    ]
    
    print("=" * 60)
    print("KEYWORD EXTRACTION VERIFICATION")
    print("=" * 60)
    
    for scenario in scenarios:
        query = scenario["input"]
        # In a real environment, this calls LLM. 
        # For this verification, we want to see the LLM's actual performance if possible,
        # otherwise we'd mock it. Since I have API keys, I'll let it run.
        
        try:
            keyword = await KeywordExtractor.extract(query)
            print(f"Input:    '{query}'")
            print(f"Extracted: '{keyword}' (Expected: '{scenario['expected']}')")
            print("-" * 40)
        except Exception as e:
            print(f"Error extracting for '{query}': {e}")

if __name__ == "__main__":
    asyncio.run(test_extraction())
