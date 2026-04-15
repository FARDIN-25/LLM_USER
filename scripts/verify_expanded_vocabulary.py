import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.application.query_expansion.tax_vocabulary import expand_query

def test_expansion():
    # Test a newly integrated term
    test_term = "export import gst"
    print(f"Testing expansion for '{test_term}'...")
    try:
        result = expand_query(test_term)
        print("Success!")
        print(f"Matched concepts: {result.get('matched_concepts', [])}")
        print(f"Expanded queries: {result.get('expanded_queries', [])}")
        
        # Verify it matched something from IGST_CORE
        if any("export" in c for c in result.get('matched_concepts', [])) or \
           any("igst" in c for c in result.get('matched_concepts', [])):
            print("VERIFICATION PASSED: Found integrated terms.")
        else:
            print("VERIFICATION FAILED: Integrated terms not found in expansion.")
            
    except Exception as e:
        print(f"FAILED with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_expansion()
