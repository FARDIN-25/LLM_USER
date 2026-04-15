# src/rag_service/application/query_rewriter.py
import logging
from typing import List, Dict, Any, Optional
from src.rag_service.infrastructure.mistral import (
    async_call_openrouter_chat, 
    async_call_mistral_chat
)
from src.shared.config import settings

logger = logging.getLogger("fintax")

class QueryRewriter:
    """
    Rewrites follow-up queries into standalone search queries using conversation history.
    """

    PROMPT_TEMPLATE = """ROLE:
You are a senior query rewriting engine for a production-grade Retrieval-Augmented Generation (RAG) system specialized in Tax, GST, and Legal domains.

OBJECTIVE:
Rewrite the user query into a concise, precise, and standalone search query that maximizes retrieval accuracy for Full-Text Search (FTS) and Semantic Vector Search.

INPUT:
Chat History:
{chat_history}

User Query:
{user_query}

---

STRICT RULES (MANDATORY):

1. FOLLOW-UP & LATENT CONTEXT RESOLUTION
- Resolve pronouns (it, he, him, this, these) using the context.
- IMPORTANT: If the query is an incomplete concept (e.g., "eligibility", "process", "due date") but lacks a subject, identify the subject from the most recent tax-related entity in the chat history.
- Do NOT assume or invent details that are not in the input.

2. KEEP IT SHORT (CRITICAL)
- Output must be between 3 to 10 words.
- Never generate long sentences.

3. NO HALLUCINATION
- Do NOT introduce concepts or terminology not present in the user query or chat history.
- Use only terms that actually appeared in the conversation.

4. PRESERVE INTENT EXACTLY
- Do NOT shift the domain or change the legal/tax meaning.

5. OPTIMIZED FOR SEARCH
- Use search-friendly phrasing suitable for keyword matching and embeddings.
- Avoid all filler words and markdown (NO **bold**, NO # headings).

6. MINIMAL REWRITE POLICY
- If the query is already clear and standalone, RETURN IT AS-IS.
- Rewrite ONLY when context from the history is required.

7. NO EXTRA OUTPUT
- Return ONLY the final rewritten search query.

---

EXAMPLES:

Chat History:
User: What is Input Tax Credit (ITC)?
User Query: eligibility
Output:
ITC eligibility rules

---

Chat History:
User: Tell me about Section 80C deductions.
User Query: what are the limits
Output:
Section 80C deduction limits

---

Chat History:
User: GSTR-3B filing process
User Query: due date for this month
Output:
GSTR-3B filing due date

---

Chat History:
User: who is bhaaskar
User Query: tell me about him
Output:
who is bhaaskar

---

Chat History:
(empty)
User Query: how to file GST returns
Output:
how to file GST returns
"""

    @classmethod
    async def rewrite(cls, query: str, chat_history: List[Dict[str, Any]]) -> str:
        """
        Rewrites and normalizes the query using LLM, returning an ultra-concise string.
        """
        # Format chat history for prompt
        if not chat_history:
            history_text = "(empty)"
        else:
            history_text = ""
            # Dynamic history turns and content length from settings
            history_limit = settings.REWRITE_HISTORY_TURNS
            content_limit = settings.REWRITE_CONTENT_CHARS
            
            for msg in chat_history[-history_limit:]: 
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")[:content_limit]
                history_text += f"{role}: {content}\n"
            
        prompt = cls.PROMPT_TEMPLATE.format(
            chat_history=history_text,
            user_query=query
        )
        
        try:
            raw_response = ""
            
            # --- PHASE 1: MISTRAL FIRST ---
            if settings.MISTRAL_ENABLED and settings.MISTRAL_API_KEY:
                try:
                    response = await async_call_mistral_chat(
                        prompt_text=prompt,
                        api_key=str(settings.MISTRAL_API_KEY),
                        model=settings.MISTRAL_MODEL,
                        timeout=10
                    )
                    raw_response = response.get("content", "").strip()
                except Exception as me:
                    logger.warning(f"Mistral rewrite failed, falling back to OpenRouter: {me}")
            
            # --- PHASE 2: OPENROUTER FALLBACK ---
            if not raw_response and settings.OPENROUTER_API_KEY:
                response = await async_call_openrouter_chat(
                    prompt_text=prompt,
                    api_key=str(settings.OPENROUTER_API_KEY),
                    model=settings.OPENROUTER_MODEL,
                    timeout=10
                )
                raw_response = response.get("content", "").strip()

            if raw_response:
                # Clean any common artifacts if the model provides them (e.g. quotes or <rewritten_query> tags)
                clean_response = raw_response.replace("<rewritten_query>", "").replace("</rewritten_query>", "").strip()
                # Remove any leading "Output:" or "Rewritten Query:" if the model hallucinated them
                if clean_response.lower().startswith("output:"):
                    clean_response = clean_response[7:].strip()
                elif clean_response.lower().startswith("rewritten query:"):
                    clean_response = clean_response[16:].strip()
                
                # 🔥 VALIDATION
                words = clean_response.split()
                
                # Rule 1: Length check (Min 2, Max 10)
                if len(words) < 2 or len(words) > 10:
                    clean_response = query
                
                # Rule 2: Blocked words (avoid common transition/explanation terms)
                blocked = ["including", "such as", "and more", "etc"]
                if any(b in clean_response.lower() for b in blocked):
                    clean_response = query
                
                # Rule 3: Expansion limit (prevent excessive hallucination/explanation)
                if len(clean_response) > len(query) * 2:
                    clean_response = query

                logger.info(f"🔄 Query rewritten: '{query}' -> '{clean_response}'")
                return clean_response

        except Exception as e:
            logger.warning(f"LLM query rewritten failed: {e}")
            
        return query

def get_query_rewriter():
    return QueryRewriter()
