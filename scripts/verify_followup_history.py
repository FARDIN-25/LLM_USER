# scripts/verify_followup_history.py
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chat_service.application.chat_service import ChatService
from src.shared import schemas

class TestFollowupHistory(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.chat_service = ChatService(self.db)

    @patch('src.chat_service.application.chat_service.call_mistral_chat')
    @patch('src.chat_service.application.chat_service.detect_template_from_question')
    async def test_history_passed_to_generation(self, mock_detect, mock_call_llm):
        # Mocking
        mock_detect.return_value = ("rag", {"user_query": "Tell me more about GST"})
        mock_call_llm.return_value = {"content": "Answer: Here is more about GST...", "model": "mistral-tiny"}
        
        # Test Payload
        payload = schemas.QueryCreate(
            question="Tell me more",
            session_id="test-session",
            user_id="test-user"
        )
        
        # We need to mock _retrieve_documents and other internal methods or just test _generate_answer directly
        # Let's test _generate_answer directly for simplicity of prompt verification
        
        query = "Tell me more about GST"
        context = "GST was introduced in 2017..."
        history = "User: What is GST?\nAssistant: GST is a tax."
        
        result = await self.chat_service._generate_answer(
            query=query,
            context=context,
            chunks=[],
            important_words=[],
            chat_history=history
        )
        
        # Verify call_mistral_chat received history
        args, kwargs = mock_call_llm.call_args
        prompt = args[0]
        
        print("\nGenerated Prompt Snippet:")
        print("-" * 20)
        print(prompt[:800])
        print("-" * 20)
        
        self.assertIn("🧠 CONVERSATION HISTORY:", prompt)
        self.assertIn("📚 CONTEXT:", prompt)
        self.assertIn("❓ USER QUESTION:", prompt)
        self.assertIn("🎯 INSTRUCTIONS:", prompt)
        self.assertIn("User: What is GST?", prompt)
        self.assertIn("Assistant: GST is a tax.", prompt)
        self.assertIn("Continue from the previous answer", prompt)
        self.assertIn("✅ OUTPUT FORMAT:", prompt)

async def run_test():
    test = TestFollowupHistory()
    test.setUp()
    await test.test_history_passed_to_generation()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_test())
