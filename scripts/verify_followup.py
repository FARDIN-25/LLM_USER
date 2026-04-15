# scripts/verify_followup.py
import sys
import os
import logging

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.followup_service.domain.followup_detector import FollowupDetector
from src.followup_service.domain.followup_rewriter import FollowupRewriter
from src.shared.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fintax-test")

def test_scenarios():
    scenarios = [
        {
            "name": "Pronoun Resolution",
            "prev_query": "What is GST?",
            "curr_query": "How much is its rate?",
            "history": "User: What is GST?\nAssistant: GST is Goods and Services Tax.",
            "expected_is_followup": True
        },
        {
            "name": "Ambiguous Continuation",
            "prev_query": "Explain TDS on rent.",
            "curr_query": "Tell me more.",
            "history": "User: Explain TDS on rent.\nAssistant: TDS on rent is applicable at 10% for individuals.",
            "expected_is_followup": True
        },
        {
            "name": "Standalone Query",
            "prev_query": "What is GST?",
            "curr_query": "How to file ITR?",
            "history": "User: What is GST?\nAssistant: GST is Goods and Services Tax.",
            "expected_is_followup": False
        },
        {
            "name": "Entity Overlap (Implicit Follow-up)",
            "prev_query": "Tell me about Section 80C.",
            "curr_query": "What are the limits?",
            "history": "User: Tell me about Section 80C.\nAssistant: Section 80C allows deductions up to 1.5 lakhs.",
            "expected_is_followup": True
        }
    ]

    print(f"\n{'='*60}")
    print(f"FOLLOW-UP VERIFICATION TEST")
    print(f"{'='*60}\n")

    with open('scripts/followup_results.txt', 'w', encoding='utf-8') as f:
        f.write(f"{'='*60}\n")
        f.write("FOLLOW-UP VERIFICATION TEST\n")
        f.write(f"{'='*60}\n\n")

        for s in scenarios:
            f.write(f"Scenario: {s['name']}\n")
            f.write(f"  Prev Query: {s['prev_query']}\n")
            f.write(f"  Curr Query: {s['curr_query']}\n")
            
            # 1. Test Detector
            is_followup = FollowupDetector.is_followup(s['curr_query'], previous_query=s['prev_query'])
            f.write(f"  Is Follow-up detected: {is_followup} (Expected: {s['expected_is_followup']})\n")
            
            # 2. Test Rewriter
            if is_followup:
                rewritten = FollowupRewriter.rewrite(s['history'], s['curr_query'])
                f.write(f"  Rewritten Query: '{rewritten}'\n")
            else:
                f.write("  (Skipping rewrite)\n")
            
            f.write("-" * 40 + "\n")
            print(f"Scenario: {s['name']} - Done")

    print("\nResults written to scripts/followup_results.txt")

if __name__ == "__main__":
    if not settings.MISTRAL_API_KEY:
        print("WARNING: MISTRAL_API_KEY not set. Rewriting will fallback to original query.")
    
    test_scenarios()
