"""
Multi-language response service: generate or wrap English + Tamil responses.
Production-ready: optional LLM-based Tamil translation; fallback to English-only.
"""
import os
import logging
from typing import Dict, Optional
from src.shared.config import settings

logger = logging.getLogger("fintax")


def get_bilingual_response(
    english_text: str,
    request_tamil: bool = True,
    openrouter_api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, str]:
    """
    Return language_response dict with keys 'english' and optionally 'tamil'.
    If request_tamil and API available, attempts to translate to Tamil; else tamil = "" or copy.
    """
    result = {"english": (english_text or "").strip(), "tamil": ""}
    if not result["english"]:
        return result

    if not request_tamil:
        return result

    api_key = openrouter_api_key or settings.OPENROUTER_API_KEY
    model = model or settings.OPENROUTER_MODEL

    if not api_key:
        logger.debug("Multilang: OPENROUTER_API_KEY not set; skipping Tamil translation")
        return result

    try:
        from ..infrastructure.openrouter import call_openrouter_chat
        prompt = (
            "Translate the following English text to Tamil. "
            "Return only the Tamil translation, no explanation. Keep technical terms (e.g. GST, IT) as-is if commonly used.\n\n"
            f"{result['english'][:3000]}"
        )
        resp = call_openrouter_chat(prompt, api_key, model, timeout=15)
        tamil = (resp.get("content") or "").strip()
        if tamil:
            result["tamil"] = tamil
    except Exception as e:
        logger.warning("Multilang: Tamil translation failed: %s", e)
    return result


def build_language_response(
    answer: str,
    language_hint: Optional[str] = None,
    include_tamil: bool = True,
) -> Dict[str, str]:
    """
    Build language_response for storage. If language_hint is 'tamil', request Tamil.
    """
    request_tamil = include_tamil and (language_hint in ("tamil", "ta", "tm"))
    return get_bilingual_response(english_text=answer, request_tamil=request_tamil)
