"""
OpenRouter API service for LLM calls.
"""
import logging
import requests
from typing import Dict, Any
from fastapi import HTTPException

from app.services.llm_service import detect_language

logger = logging.getLogger("fintax")


def call_openrouter_chat(prompt_text: str, api_key: str, model: str, timeout: int = 30) -> Dict[str, Any]:
    """Call OpenRouter API with the given prompt."""
    if not api_key:
        error_msg = "Missing OPENROUTER_API_KEY in .env file. Please set OPENROUTER_API_KEY environment variable."
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    
    if not api_key.strip():
        error_msg = "OPENROUTER_API_KEY is empty. Please set a valid API key in .env file."
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

    headers = {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8001",
        "X-Title": "LLM User Service"
    }

    # Detect language from prompt to add system message if needed
    question_lang = detect_language(prompt_text)
    
    messages = []
    if question_lang == "tamil":
        # Add strong system message for Tamil responses
        messages.append({
            "role": "system",
            "content": """You are a professional tax assistant for Indian taxation and GST.

CRITICAL LANGUAGE REQUIREMENT:
- When the user asks in Tamil (தமிழ்), you MUST respond ENTIRELY in Tamil language
- Write your complete answer using Tamil script
- Do NOT respond in English if the question is in Tamil
- Provide detailed, comprehensive answers in Tamil
- Use proper Tamil grammar and vocabulary
- If technical terms are needed, use Tamil translations with English in parentheses

Your response must be 100% in Tamil when the question is in Tamil."""
        })
    messages.append({"role": "user", "content": prompt_text})
    
    # Increase max_tokens for Tamil responses to ensure complete answers
    max_tokens = 2500 if question_lang == "tamil" else 2000
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens
    }

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=timeout
        )

        # Non-JSON response check
        try:
            response_data = resp.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as json_error:
            logger.error(f"❌ LLM returned non-JSON response. Status: {resp.status_code}, Text: {resp.text[:500]}")
            raise HTTPException(
                status_code=502,
                detail=f"LLM returned non-JSON response: {resp.text[:200]}"
            )

        if not resp.ok:
            error_detail = "Unknown error"
            try:
                error_json = response_data if isinstance(response_data, dict) else {}
                error_detail = error_json.get("error", {}).get("message", resp.text) if isinstance(error_json.get("error"), dict) else resp.text
            except:
                error_detail = resp.text
            logger.error(f"❌ OpenRouter API error {resp.status_code}: {error_detail}")
            raise HTTPException(
                status_code=502,
                detail=f"OpenRouter API error {resp.status_code}: {error_detail}"
            )
        
        if "choices" not in response_data or not response_data["choices"]:
            logger.error("❌ Invalid response format from OpenRouter - no choices found. Response: %s", str(response_data)[:500])
            raise HTTPException(
                status_code=502,
                detail=f"Invalid LLM response: No choices in response."
            )

        # Safely extract message content
        try:
            first_choice = response_data["choices"][0]
            if not first_choice:
                raise HTTPException(status_code=502, detail="Empty choice in LLM response")
            
            message_obj = first_choice.get("message")
            if not message_obj:
                raise HTTPException(status_code=502, detail="No message object in LLM response choice")
            
            message_content = message_obj.get("content") if isinstance(message_obj, dict) else ""
            if message_content is None:
                message_content = ""
        except HTTPException:
            raise
        except (KeyError, IndexError, AttributeError) as e:
            logger.error("❌ Error parsing OpenRouter response: %s", str(e))
            raise HTTPException(status_code=502, detail=f"Error parsing LLM response: {str(e)}")
        
        usage = response_data.get("usage", {}) or {}
        
        # Ensure message_content is a string
        if not isinstance(message_content, str):
            message_content = str(message_content) if message_content else ""
        
        # Clean up common token artifacts
        if message_content:
            message_content = message_content.replace("BOS", "").replace("EOS", "").strip()
        
        result = {
            "content": message_content or "",
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
                "completion_tokens": usage.get("completion_tokens", 0) or 0,
                "total_tokens": usage.get("total_tokens", (usage.get("prompt_tokens", 0) or 0) + (usage.get("completion_tokens", 0) or 0)) or 0,
            },
            "model": response_data.get("model") or model,
            "id": response_data.get("id"),
        }
        
        return result

    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        logger.error(f"❌ LLM request timeout after {timeout} seconds")
        raise HTTPException(status_code=504, detail=f"LLM timeout after {timeout} seconds")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error calling LLM: {e}")
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Unexpected error calling LLM: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

