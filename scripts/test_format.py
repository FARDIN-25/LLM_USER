
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.application.query_rewriter import QueryRewriter

def test_format():
    print("Testing QueryRewriter.PROMPT_TEMPLATE.format()...")
    try:
        q = "test query"
        h = "test history"
        prompt = QueryRewriter.PROMPT_TEMPLATE.format(
            chat_history=h,
            query=q
        )
        print("Format successful!")
    except KeyError as e:
        print(f"KeyError: {e}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_format()
