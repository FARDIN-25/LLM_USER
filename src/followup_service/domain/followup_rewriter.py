import logging
from src.shared.config import settings
from src.rag_service.infrastructure.mistral import (
    async_call_openrouter_chat, 
    async_call_mistral_chat
)

logger = logging.getLogger("fintax")

class FollowupRewriter:
    """
    Rewrites a follow-up question so it becomes a standalone question 
    using the LLM service.
    """

    PROMPT_TEMPLATE = """ROLE:
You are a senior query rewriting engine for a production-grade Retrieval-Augmented Generation (RAG) system specialized in Tax, GST, and Legal domains.

OBJECTIVE:
Rewrite the user query into a concise, precise, and standalone search query that maximizes retrieval accuracy for Full-Text Search (FTS) and Semantic Vector Search.

STRICT RULES (MANDATORY):

1. FOLLOW-UP & LATENT CONTEXT RESOLUTION
- Resolve pronouns (it, he, him, this, these) using the conversation history.
- If the query is an incomplete concept (e.g., "eligibility", "process", "due date") but lacks a subject, identify the subject from the most recent tax-related entity in the history.
- Do NOT assume or invent details that are not in the input.

2. KEEP IT SHORT (CRITICAL)
- Output must be between 3 to 10 words.
- Never generate long sentences.

3. NO HALLUCINATION
- Do NOT introduce concepts or terminology not present in the user query or history.
- Use only terms that actually appeared in the conversation.

4. PRESERVE INTENT EXACTLY
- Do NOT shift the domain or change the legal/tax meaning.

5. OPTIMIZED FOR SEARCH
- Use search-friendly phrasing suitable for keyword matching and embeddings.
- Avoid all filler words and markdown (NO **bold**, NO # headings).

6. NO EXTRA OUTPUT
- Return ONLY the final rewritten search query.

7. LANGUAGE CONSISTENCY (CRITICAL)
- Always rewrite the query in the SAME language as the original USER QUERY.
- If the USER QUERY is in English, the output MUST be in English.
- Do NOT translate the query into a language found in the HISTORY if the USER QUERY is in a different language.

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

CONVERSATION HISTORY:
{history}

USER QUERY:
{question}
"""

    @classmethod
    async def rewrite(cls, history_text: str, current_question: str) -> str:
        if not history_text:
            return current_question

        prompt = cls.PROMPT_TEMPLATE.format(
            history=history_text,
            question=current_question,
        )

        model_setting = getattr(settings, "REWRITE_MODEL", settings.OPENROUTER_MODEL)
        model = str(model_setting) if model_setting else str(settings.OPENROUTER_MODEL)

        try:
            # --- PHASE 1: MISTRAL FIRST ---
            if settings.MISTRAL_ENABLED and settings.MISTRAL_API_KEY:
                try:
                    response = await async_call_mistral_chat(
                        prompt_text=prompt,
                        api_key=str(settings.MISTRAL_API_KEY),
                        model=settings.MISTRAL_MODEL,
                        timeout=10
                    )
                    rewritten = response.get("content", "").strip()
                    if rewritten:
                        logger.info(f"🔄 Follow-up Rewritten (Mistral): '{current_question}' -> '{rewritten}'")
                        return rewritten
                except Exception as me:
                    logger.warning(f"Mistral follow-up rewrite failed, falling back to OpenRouter: {me}")

            # --- PHASE 2: OPENROUTER FALLBACK ---
            if settings.OPENROUTER_API_KEY:
                model_setting = getattr(settings, "REWRITE_MODEL", settings.OPENROUTER_MODEL)
                model = str(model_setting) if model_setting else str(settings.OPENROUTER_MODEL)
                
                response = await async_call_openrouter_chat(
                    prompt_text=prompt,
                    api_key=str(settings.OPENROUTER_API_KEY),
                    model=model,
                    timeout=10
                )
                rewritten = response.get("content", "").strip()
                if rewritten:
                    logger.info(f"🔄 Follow-up Rewritten (OpenRouter): '{current_question}' -> '{rewritten}'")
                    return rewritten

            logger.warning("No LLM API keys configured or calls failed for follow-up rewriting")
            return current_question

        except Exception as e:
            logger.warning(f"Failed to rewrite follow-up question: {e}")

        return current_question