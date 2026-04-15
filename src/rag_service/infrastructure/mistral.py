"""
MISTRAL API service for LLM calls.
"""
import logging
import random
import time
import requests
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import HTTPException

from .llm_service import detect_language
from src.shared.config import settings

logger = logging.getLogger("fintax")

# ── ENDPOINT ────────────────────────────────────────────────────────────────
MISTRAL_CHAT_COMPLETIONS_URL = "https://api.mistral.ai/v1/chat/completions"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── RETRY CONFIG ─────────────────────────────────────────────────────────────
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 2
MAX_RETRY_DELAY = 15
RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]

# ── MODEL TRUE LIMITS (ministral-8b-2512 official) ───────────────────────────
# Used for safety checks/caps (we still keep an app "safe default" below).
MODEL_MAX_CONTEXT_TOKENS = 262_144
MODEL_MAX_OUTPUT_TOKENS = 16_000

# ── APP SAFE DEFAULTS ─────────────────────────────────────────────────────────
# We intentionally do NOT try to use the full 262k window; we keep a stable
# production budget to avoid latency/cost spikes and truncation edge cases.
MAX_MODEL_TOKENS = 32_000
SAFETY_BUFFER = 500
MIN_OUTPUT_TOKENS = 300
MAX_OUTPUT_TOKENS = 80000

# ── RAG CHUNKING SAFETY (guard rails; prompt builders may exceed) ─────────────
MAX_CONTEXT_CHARS = 60_000

# ── CONNECTION REUSE (enterprise: lower latency, fewer handshake failures) ───
_session = requests.Session()
_async_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=120.0), follow_redirects=True)


def _parse_prompt_for_chat(prompt_text: str) -> tuple[str, Optional[str]]:
    """
    Parse prompt to extract system role and user content for better chat model integration.
    Returns (user_content, system_content).
    """
    system_content = None
    user_content = prompt_text
    
    # now detect the language
    question_lang = detect_language(user_content)

    # Check if prompt contains SYSTEM ROLE section (from enterprise prompt template)
    if "SYSTEM ROLE:" in prompt_text:
        # Extract system role and rules
        system_start = prompt_text.find("SYSTEM ROLE:")

        # Find CONTEXT section (support multiple header variants)
        context_start = -1
        for header in ["CONTEXT (INTERNAL —", "CONTEXT (INTERNAL -", "CONTEXT (INTERNAL", "CONTEXT:"]:
            context_start = prompt_text.find(header)
            if context_start != -1:
                break

        user_question_start = prompt_text.find("USER QUESTION:")
        final_answer_start = prompt_text.find("FINAL ANSWER:")
        
        if system_start != -1 and user_question_start != -1:
            # Extract system content (from SYSTEM ROLE to CONTEXT, or to USER QUESTION if no CONTEXT)
            # System should only contain rules, NOT the KB context
            if context_start != -1 and context_start > system_start:
                # Extract system content up to CONTEXT section (rules only)
                system_section = prompt_text[system_start:context_start].replace("SYSTEM ROLE:", "").strip()
            else:
                # No CONTEXT section, extract up to USER QUESTION
                system_section = prompt_text[system_start:user_question_start].replace("SYSTEM ROLE:", "").strip()
            
            # Extract CONTEXT section (KB data / "Our Data's") - MUST be in user message so LLM uses it
            context_section = ""
            if context_start != -1 and context_start < user_question_start:
                # Find where CONTEXT section ends (before USER QUESTION)
                context_end = prompt_text.find("\n\nUSER QUESTION:", context_start)
                if context_end == -1:
                    context_end = prompt_text.find("\nUSER QUESTION:", context_start)
                if context_end == -1:
                    context_end = user_question_start
                # Raw slice: CONTEXT header + body
                context_text = prompt_text[context_start:context_end]
                # Remove CONTEXT header line (handle all variants)
                context_section = context_text
                for h in [
                    "CONTEXT (INTERNAL — DO NOT MENTION):",
                    "CONTEXT (INTERNAL - DO NOT MENTION):",
                    "CONTEXT (INTERNAL):",
                    "CONTEXT:",
                ]:
                    context_section = context_section.replace(h, "").strip()
                # If stripping left empty but we have content (e.g. encoding), use content after first line (header)
                if not context_section.strip() and context_text.strip():
                    lines = context_text.split("\n", 1)
                    context_section = (lines[1].strip() if len(lines) > 1 else context_text).strip()

            # Enterprise safety: cap very large context blocks (prevents runaway prompts)
            if context_section and len(context_section) > MAX_CONTEXT_CHARS:
                context_section = context_section[:MAX_CONTEXT_CHARS].rsplit("\n", 1)[0]
                logger.debug("🧱 Context capped to %d chars", MAX_CONTEXT_CHARS)
            
            # Extract user question
            if final_answer_start != -1:
                user_question_section = prompt_text[user_question_start:final_answer_start].replace("USER QUESTION:", "").strip()
            else:
                user_question_section = prompt_text[user_question_start:].replace("USER QUESTION:", "").strip()
            
            # Always combine CONTEXT + USER QUESTION for user message (Our Data's must be in user message)
            if context_section and context_section.strip():
                user_content = f"{context_section.strip()}\n\n{user_question_section}"
            else:
                user_content = user_question_section
            
            # Set system content (rules only, no KB data)
            system_content = system_section

    if not system_content and question_lang == "tamil":
        # Add strong system message for Tamil responses
        system_content = """You are a professional tax assistant for Indian taxation and GST.

CRITICAL LANGUAGE REQUIREMENT:
- When the user asks in Tamil (தமிழ்), you MUST respond ENTIRELY in Tamil language
- Write your complete answer using Tamil script
- Do NOT respond in English if the question is in Tamil
- Provide detailed, comprehensive answers in Tamil
- Use proper Tamil grammar and vocabulary
- If technical terms are needed, use Tamil translations with English in parentheses

Your response must be 100% in Tamil when the question is in Tamil."""

    return user_content, system_content


def _parse_retry_after_seconds(value: str) -> int:
    """
    Retry-After can be delta-seconds or an HTTP-date. We only reliably support
    delta-seconds here; otherwise fall back to backoff.
    """
    if not value:
        return 0
    try:
        secs = int(str(value).strip())
        return max(0, min(secs, MAX_RETRY_DELAY))
    except Exception:
        return 0


def _compute_backoff_delay(attempt: int, resp: requests.Response | None) -> float:
    base = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
    retry_after = 0
    try:
        if resp is not None:
            retry_after = _parse_retry_after_seconds(resp.headers.get("Retry-After", "") or "")
    except Exception:
        retry_after = 0
    delay = float(max(base, retry_after))
    # Add a small jitter to avoid thundering herd.
    jitter = delay * random.uniform(0.0, 0.25)
    return min(delay + jitter, float(MAX_RETRY_DELAY))


def call_mistral_chat(prompt_text: str, api_key: str, model: str, timeout: int = 120) -> Dict[str, Any]:
    """Call MISTRAL API with the given prompt."""
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="MISTRAL_API_KEY is missing or empty in .env file."
        )
    
    if not api_key.strip():
        raise HTTPException(
            status_code=500,
            detail="MISTRAL_API_KEY is missing or empty in .env file."
        )

    headers = {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
        # Official Mistral API doesn't require HTTP-Referer / X-Title
    }
    
    # Parse prompt to extract system role and user content
    messages = []
    user_content, system_content = _parse_prompt_for_chat(prompt_text)
    
    # Add system message
    if system_content:
        messages.append({
            "role": "system",
            "content": system_content
        })
    
    # Debug logging for computation template prompts
    if "REQUIRED RESPONSE FORMAT" in prompt_text or "Formula Used" in prompt_text:
        logger.info(f"🔍 [COMPUTATION DEBUG] Prompt contains computation format instructions")
    
    # Add user message
    messages.append({"role": "user", "content": user_content})
    
    # Dynamic max token control: keep a stable production budget.
    # KEY FIX: compute with MAX_MODEL_TOKENS=32,000 so available_tokens doesn't collapse to near-zero.
    approx_prompt_tokens = len(user_content + (system_content or "")) // 4
    available_tokens = max(0, MAX_MODEL_TOKENS - SAFETY_BUFFER - approx_prompt_tokens)

    # ✅ FIXED TOKEN LOGIC
    max_tokens = min(MAX_OUTPUT_TOKENS, available_tokens)

    if max_tokens < 100:
        max_tokens = 100  # minimum safe output
        logger.debug(
            "🔢 Token budget: prompt_chars=%d approx_tokens=%d available=%d max_tokens=%d",
            len(prompt_text), approx_prompt_tokens, available_tokens, max_tokens
        )
 
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,  # Stable configuration for consistent RAG answers
        "max_tokens": max_tokens
    }

    # Retry logic for transient errors
    resp = None
    response_data = None
    ttft_ms = 0
    finish_reason = ""
    
    for attempt in range(MAX_RETRIES):
        try:
            # Track TTFT (Time To First Token) - measure time from request start to response received
            llm_request_start = time.time()
            resp = _session.post(
                MISTRAL_CHAT_COMPLETIONS_URL,
                headers=headers,
                json=data,
                # Enterprise: separate connect/read timeouts; keep signature backward compatible.
                timeout=(10, timeout)
            )
            llm_request_end = time.time()
            ttft_ms = int((llm_request_end - llm_request_start) * 1000)

            # Non-JSON response check
            try:
                response_data = resp.json()
            except (ValueError, requests.exceptions.JSONDecodeError) as json_error:
                logger.error(f"❌ LLM returned non-JSON response. Status: {resp.status_code}, Text: {resp.text[:500]}")
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM returned non-JSON response: {resp.text[:200]}"
                )

            # Check if we got a retryable error
            if not resp.ok:
                error_detail = "Unknown error"
                try:
                    error_json = response_data if isinstance(response_data, dict) else {}
                    error_detail = error_json.get("error", {}).get("message", resp.text) if isinstance(error_json.get("error"), dict) else resp.text
                except:
                    error_detail = resp.text
                
                # Check if this is a retryable error
                status_code = int(resp.status_code)  # Ensure it's an integer
                if status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                    delay = _compute_backoff_delay(attempt, resp)
                    # Use debug level to avoid cluttering terminal with retry messages
                    logger.debug(
                        f"MISTRAL API error {status_code} (attempt {attempt + 1}/{MAX_RETRIES}): {error_detail[:100]}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    continue  # Retry the request
                else:
                    # Non-retryable error or max retries reached
                    req_id = (resp.headers.get("x-request-id") or resp.headers.get("x-requestid") or "").strip()
                    req_suffix = f" (request_id={req_id})" if req_id else ""
                    msg = f"MISTRAL API error {status_code}: {error_detail}{req_suffix}".replace("errror", "error")
                    if attempt == MAX_RETRIES - 1:
                        msg += f" (after {MAX_RETRIES} attempts)"
                    logger.error(f"❌ {msg}")
                    raise HTTPException(status_code=502, detail=msg)
            
            # Success - break out of retry loop
            break
            
        except HTTPException:
            # Re-raise HTTP exceptions immediately (non-retryable)
            raise
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                delay = _compute_backoff_delay(attempt, None)
                logger.debug(f"LLM request timeout (attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {delay}s...")
                time.sleep(delay)
                continue
            else:
                logger.error(f"❌ LLM request timeout after {timeout} seconds (after {MAX_RETRIES} attempts)")
                raise HTTPException(status_code=504, detail=f"LLM timeout after {timeout} seconds")
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                delay = _compute_backoff_delay(attempt, None)
                logger.debug(f"Network error (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)[:100]}. Retrying in {delay}s...")
                time.sleep(delay)
                continue
            else:
                logger.error(f"❌ Network error calling LLM after {MAX_RETRIES} attempts: {e}")
                raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    
    # Verify we have a successful response
    if resp is None or not resp.ok or response_data is None:
        error_detail = "Request failed after all retries"
        if resp is not None:
            try:
                error_json = response_data if isinstance(response_data, dict) else {}
                error_detail = error_json.get("error", {}).get("message", resp.text) if isinstance(error_json.get("error"), dict) else resp.text
            except:
                error_detail = resp.text if resp else "No response received"
        msg = f"MISTRAL API error: {error_detail} (after {MAX_RETRIES} attempts)".replace("errror", "error")
        logger.error(f"❌ {msg}")
        raise HTTPException(status_code=502, detail=msg)
    
    # Process successful response
    if "choices" not in response_data or not response_data["choices"]:
        logger.error("❌ Invalid response format from MISTRAL - no choices found. Response: %s", str(response_data)[:500])
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

        finish_reason = first_choice.get("finish_reason", "") or ""
        if finish_reason == "length":
            logger.warning(
                "⚠️ Answer truncated at max_tokens=%d. Consider increasing MAX_OUTPUT_TOKENS.",
                max_tokens
            )
    except HTTPException:
        raise
    except (KeyError, IndexError, AttributeError) as e:
        logger.error("❌ Error parsing MISTRAL response: %s", str(e))
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
            "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0,
        },
        "model": response_data.get("model") or model,
        "id": response_data.get("id"),
        "ttft_ms": ttft_ms,
    }

    if getattr(settings, "LOG_LLM_USAGE", True):
        u = result["usage"]
        logger.info(
            "LLM | model=%s ttft=%dms prompt=%d completion=%d total=%d cached=%d max_tokens=%d finish=%s",
            result["model"], ttft_ms,
            u["prompt_tokens"], u["completion_tokens"], u["total_tokens"], u["cached_tokens"],
            max_tokens, finish_reason
        )
        if u["cached_tokens"] > 0:
            logger.info("✨ LLM CACHE HIT: Reused %d tokens (90%% cheaper!)", u["cached_tokens"])
    
    return result


def call_openrouter_chat(prompt_text: str, api_key: str, model: str, timeout: int = 60) -> Dict[str, Any]:
    """Call OpenRouter API with the given prompt."""
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY is missing")

    headers = {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
        "HTTP-Referer": "https://fintax.ai", # Optional
        "X-Title": "FinTax Tax Assistant", # Optional
    }

    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}]
    }

    try:
        resp = _session.post(OPENROUTER_CHAT_COMPLETIONS_URL, headers=headers, json=data, timeout=timeout)
        resp.raise_for_status()
        response_data = resp.json()
        
        if "choices" not in response_data or not response_data["choices"]:
            raise HTTPException(status_code=502, detail="Invalid OpenRouter response")

        return {
            "content": response_data["choices"][0]["message"]["content"],
            "usage": response_data.get("usage", {}),
            "model": response_data.get("model", model)
        }
    except Exception as e:
        logger.error(f"OpenRouter LLM failed: {e}")
        raise HTTPException(status_code=502, detail=f"OpenRouter LLM failed: {e}")


async def async_call_mistral_chat(prompt_text: str, api_key: str, model: str, timeout: int = 120) -> Dict[str, Any]:
    """Asynchronous call to MISTRAL API."""
    if not api_key or not api_key.strip():
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY is missing or empty.")

    user_content, system_content = _parse_prompt_for_chat(prompt_text)
    messages = []
    if system_content:
        messages.append({"role": "system", "content": system_content})
    messages.append({"role": "user", "content": user_content})

    # Token budget logic (simplified version of the sync one)
    approx_prompt_tokens = len(user_content + (system_content or "")) // 4
    available_tokens = max(0, MAX_MODEL_TOKENS - SAFETY_BUFFER - approx_prompt_tokens)
    max_tokens = min(MAX_OUTPUT_TOKENS, max(100, available_tokens))

    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for attempt in range(MAX_RETRIES):
        try:
            start_time = time.time()
            resp = await _async_client.post(
                MISTRAL_CHAT_COMPLETIONS_URL,
                headers=headers,
                json=data,
                timeout=timeout
            )
            ttft_ms = int((time.time() - start_time) * 1000)

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = _compute_backoff_delay(attempt, None) # httpx response not exactly same as requests; but delay logic is similar
                await asyncio.sleep(delay)
                continue

            resp.raise_for_status()
            response_data = resp.json()

            if "choices" not in response_data or not response_data["choices"]:
                raise HTTPException(status_code=502, detail="Invalid LLM response: No choices.")

            message_obj = response_data["choices"][0].get("message", {})
            content = (message_obj.get("content") or "").strip()
            content = content.replace("BOS", "").replace("EOS", "").strip()
            usage = response_data.get("usage", {}) or {}

            result = {
                "content": content,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
                    "completion_tokens": usage.get("completion_tokens", 0) or 0,
                    "total_tokens": usage.get("total_tokens", 0) or 0,
                    "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0,
                },
                "model": response_data.get("model") or model,
                "ttft_ms": ttft_ms,
            }

            if getattr(settings, "LOG_LLM_USAGE", True):
                u = result["usage"]
                logger.info(
                    "LLM (Async) | model=%s ttft=%dms prompt=%d completion=%d total=%d cached=%d",
                    result["model"], ttft_ms, u["prompt_tokens"], u["completion_tokens"], u["total_tokens"], u["cached_tokens"]
                )
            return result

        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                logger.error(f"❌ Async Mistral call failed after {MAX_RETRIES} attempts: {e}")
                raise HTTPException(status_code=502, detail=f"Mistral API error: {e}")
            delay = INITIAL_RETRY_DELAY * (2**attempt)
            await asyncio.sleep(delay)

    raise HTTPException(status_code=502, detail="Mistral API failed after retries")


async def async_call_openrouter_chat(prompt_text: str, api_key: str, model: str, timeout: int = 60) -> Dict[str, Any]:
    """Asynchronous call to OpenRouter API."""
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY is missing")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://fintax.ai",
        "X-Title": "FinTax Tax Assistant",
    }
    data = {"model": model, "messages": [{"role": "user", "content": prompt_text}]}

    try:
        resp = await _async_client.post(OPENROUTER_CHAT_COMPLETIONS_URL, headers=headers, json=data, timeout=timeout)
        resp.raise_for_status()
        response_data = resp.json()
        
        if "choices" not in response_data or not response_data["choices"]:
            raise HTTPException(status_code=502, detail="Invalid OpenRouter response")

        return {
            "content": response_data["choices"][0]["message"]["content"],
            "usage": response_data.get("usage", {}),
            "model": response_data.get("model", model)
        }
    except Exception as e:
        logger.error(f"Async OpenRouter LLM failed: {e}")
        raise HTTPException(status_code=502, detail=f"OpenRouter LLM failed: {e}")
