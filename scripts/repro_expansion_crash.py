import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.application.query_expansion.tax_vocabulary import expand_query

def test_expansion():
    print("Testing expansion for 'penalty' (suspected broken entry)...")
    try:
        result = expand_query("penalty")
        print("Success!")
        print(f"Result: {result}")
    except Exception as e:
        print(f"FAILED with error: {e}")

if __name__ == "__main__":
    test_expansion()
