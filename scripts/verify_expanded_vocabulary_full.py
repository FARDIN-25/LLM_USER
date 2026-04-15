import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.application.query_expansion.tax_vocabulary import expand_query

def test_expansion(test_term):
    print(f"Testing expansion for '{test_term}'...")
    try:
        result = expand_query(test_term)
        matched = result.get('matched_concepts', [])
        expansions = result.get('expanded_queries', [])
        print(f"  Matched concepts: {matched}")
        print(f"  Total expansions: {len(expansions)}")
        if matched:
            print("  SUCCESS: Matched concept(s) found.")
            return True
        else:
            print("  FAILED: No concepts matched.")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

if __name__ == "__main__":
    terms = ["export import gst", "angel tax", "tax audit threshold", "itc eligibility"]
    results = []
    print("=" * 60)
    print("COMPREHENSIVE VOCABULARY VERIFICATION")
    print("=" * 60)
    for term in terms:
        results.append(test_expansion(term))
        print("-" * 40)
    
    if all(results):
        print("FINAL VERIFICATION: ALL PASSED")
    else:
        print("FINAL VERIFICATION: SOME FAILED")
