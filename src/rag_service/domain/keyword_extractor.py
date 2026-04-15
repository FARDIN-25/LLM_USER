# src/rag_service/domain/keyword_extractor.py
import logging
from typing import Optional

from src.rag_service.infrastructure.mistral import call_openrouter_chat, call_mistral_chat
from src.shared.config import settings

logger = logging.getLogger("fintax")


class KeywordExtractor:
    """
    Extracts the most important keyword or entity from a query using an LLM.
    """

    PROMPT_TEMPLATE = """Extract the most important keyword or entity from the query.

RULES:
- Ignore stopwords (the, is, what, etc.)
- Prefer domain terms (GST, ITC, tax, etc.)
- Return a SHORT key phrase (1–4 words)
- Do NOT expand the query
- Do NOT add extra words
- Do NOT include phrases like "including", "such as", "and more"

Examples:

Input: what is gst  
Output: GST  

Input: explain input tax credit  
Output: input tax credit  

Input: tell me about gst returns  
Output: GST returns

INPUT:
{query}"""

    @classmethod
    async def extract(cls, query: str) -> str:
        if not query:
            return ""

        prompt = cls.PROMPT_TEMPLATE.format(query=query)

        try:
            # 🔹 OpenRouter (Primary)
            if settings.OPENROUTER_API_KEY:
                response = call_openrouter_chat(
                    prompt_text=prompt,
                    api_key=str(settings.OPENROUTER_API_KEY),
                    model=settings.OPENROUTER_MODEL,
                    timeout=5
                )
                keyword = response.get("content", "").strip()
                if keyword:
                    validated = cls._validate_keyword(keyword, query)
                    if validated:
                        return validated

            # 🔹 Mistral (Fallback)
            if settings.MISTRAL_ENABLED and settings.MISTRAL_API_KEY:
                response = call_mistral_chat(
                    prompt_text=prompt,
                    api_key=str(settings.MISTRAL_API_KEY),
                    model=settings.MISTRAL_MODEL,
                    timeout=5
                )
                keyword = response.get("content", "").strip()
                if keyword:
                    validated = cls._validate_keyword(keyword, query)
                    if validated:
                        return validated

        except Exception as e:
            logger.warning(f"LLM keyword extraction failed: {e}")

        # 🔹 Final fallback
        keyword = cls._fallback_extract(query)

        if len(query.split()) <= 3:
            return query.strip()

        return keyword

    @classmethod
    def _validate_keyword(cls, keyword: str, query: str) -> Optional[str]:
        """
        Validates LLM output to prevent bad or expanded keywords.
        """
        keyword = keyword.strip()

        if not keyword:
            return None

        words = keyword.split()

        # ❌ Too short or too long
        if len(words) < 1 or len(words) > 5:
            return None

        # ❌ Over-expansion
        if len(keyword) > len(query) * 1.5:
            return None

        # ❌ Bad phrases
        blocked = ["including", "such as", "and more", "etc"]
        if any(b in keyword.lower() for b in blocked):
            return None

        return keyword

    @classmethod
    def _fallback_extract(cls, query: str) -> str:
        """
        Rule-based fallback extraction.
        """
        import re

        stopwords = [
            "who", "is", "what", "tell", "about", "mr", "mrs", "ms", "dr",
            "how", "to", "explain", "the", "a", "an"
        ]

        cleaned = re.sub(r"[.,#!$%\^&\*;:{}=\-_`~()]", " ", query.lower())
        words = cleaned.split()

        filtered = [w for w in words if w not in stopwords]

        # 🔹 Return short phrase instead of single word
        return " ".join(filtered[:3]) if filtered else query.lower().strip()