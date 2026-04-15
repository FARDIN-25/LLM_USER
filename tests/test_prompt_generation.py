import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rag_service.infrastructure.prompt_templates import build_prompt_from_template

def test_gst_expert_prompt():
    print("Testing GST Expert Prompt Generation...")
    
    context = "GST Rate for services is 18%."
    query = "What is the GST rate for consulting services?"
    
    params = {
        "retrieved_context": context,
        "user_query": query,
        "important_words": ["GST", "rate", "consulting"]
    }
    
    prompt = build_prompt_from_template("gst_expert", params)
    
    # Check for persona
    assert "Senior Indian GST and General Knowledge Expert" in prompt
    # Check for context
    assert "CONTEXT:" in prompt
    assert context in prompt
    # Check for query
    assert "USER QUESTION:" in prompt
    assert query in prompt
    # Check for instructions
    assert "INSTRUCTIONS:" in prompt
    assert "RELEVANCE CHECK (CRITICAL):" in prompt
    assert "- Definition / Identification" in prompt
    # Check for variable replacements (should not contain curly braces if successful)
    assert "{retrieved_context}" not in prompt
    assert "{user_query}" not in prompt
    
    print("✅ Prompt generation produced expected content.")
    print("-" * 50)
    print("Sample Prompt Snippet:")
    print(prompt[:500] + "...")
    print("-" * 50)

if __name__ == "__main__":
    try:
        test_gst_expert_prompt()
        print("Test passed!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
