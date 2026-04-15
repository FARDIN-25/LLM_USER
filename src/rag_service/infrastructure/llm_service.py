"""
LLM Service – Language detection, RAG prompt construction,
and safe answer post-processing.
"""

import re
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger("fintax")

# ==========================================================
# MARKDOWN CLEANING
# ==========================================================

def clean_markdown_formatting(text: str) -> str:
    """
    Remove unwanted markdown formatting while preserving:
    - **bold keywords**
    - bullet points
    """
    if not text:
        return ""

    # Remove markdown headings
    text = re.sub(r'^\s*#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove __bold__ but keep **bold**
    text = re.sub(r'__([^_]+)__', r'\1', text)

    # Remove italic (*text* or _text_) but not **bold**
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_([^_]+)_(?!_)', r'\1', text)

    # Convert dash bullets to •
    text = re.sub(r'^\s*-\s+', '• ', text, flags=re.MULTILINE)

    # Remove fenced code blocks safely
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Remove markdown links
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Normalize spacing
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove emojis from answer generation (Unicode emoji ranges)
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F9FF"
        "\U00002600-\U000026FF"
        "\U00002700-\U000027BF"
        "\U0001F600-\U0001F64F"
        "\U0001F1E0-\U0001F1FF"
        "\U0001F900-\U0001F9FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\u2600-\u26FF"
        "\u2700-\u27BF"
        "\uFE00-\uFE0F"
        "\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9-\u21AA\u231A-\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA\u25AA-\u25AB\u25B6\u25C0\u25FB-\u25FE\u2614-\u2615\u2648-\u2653\u267F\u2693\u26A1\u26AA-\u26AB\u26BD-\u26BE\u26C4-\u26C5\u26CE\u26D4\u26EA\u26F2-\u26F3\u26F5\u26FA\u26FD\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733-\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763-\u2764\u2795-\u2797\u27A1\u27B0\u27BF\u2934-\u2935\u2B05-\u2B07\u2B1B-\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)

    return text.strip()


# ==========================================================
# LANGUAGE DETECTION
# ==========================================================

def detect_language(text: str) -> str:
    """
    Detect language based on Unicode blocks.
    Currently supports Tamil vs English.
    """
    if not text:
        return "english"

    if re.search(r'[\u0B80-\u0BFF]', text):
        return "tamil"

    return "english"


# ==========================================================
# INTERNAL HELPERS
# ==========================================================

def _extract_chunk_data(chunk: Any) -> tuple[str, str]:
    """
    Safely extract text + source from chunk
    Supports dict or object style.
    """
    text = ""
    source = "Unknown"

    if isinstance(chunk, dict):
        text = (
            chunk.get("text")
            or chunk.get("content")
            or chunk.get("chunk_text")
            or ""
        )
        metadata = chunk.get("metadata", {})
        if isinstance(metadata, dict):
            source = (
                metadata.get("source")
                or metadata.get("source_name")
                or metadata.get("file_path")
                or "Unknown"
            )
    else:
        text = getattr(chunk, "text", "") or getattr(chunk, "content", "")
        source = getattr(chunk, "source", "Unknown")

    return text.strip(), source


# ==========================================================
# RAG PROMPT BUILDER (ENTERPRISE)
# ==========================================================

def build_rag_prompt(
    question: str,
    chunks: List[Any],
    max_chunks: int = 5,
    max_chunk_chars: int = 1200,
) -> str:
    """
    Clean RAG prompt — NO internal layer leakage

    """

    context_blocks = []

    for chunk in chunks[:max_chunks]:
        text, _ = _extract_chunk_data(chunk)
        if not text:
            continue

        if len(text) > max_chunk_chars:
            text = text[:max_chunk_chars] + "..."

        context_blocks.append(text)

    context = "\n\n".join(context_blocks) if context_blocks else ""

    body = f"""
CONTEXT (INTERNAL — DO NOT MENTION):
{context}

USER QUESTION:
{question}

"""

    return _wrap_enterprise_prompt(body) 


def _wrap_enterprise_prompt(body: str) -> str:
    """
    FINAL SAFE PROMPT

    - Internal RAG layers are invisible

    - No reasoning or KB explanation leakage

    """

    return f"""
SYSTEM ROLE:
You are a professional Indian Tax and GST Assistant.

The user message below contains: (1) relevant context from the knowledge base (Our Data's), (2) the user's question. Use that context to answer the question.

STRICT RULES (MANDATORY):
- Answer ONLY the user's question using the context provided in the user message.
- Use the provided information silently to ensure correctness.
- Format your answer with:
  - An introductory paragraph summarizing key findings (bold important dates, document names, notification numbers)
  - Numbered sections with bold titles (e.g., "1. Key Details:", "2. Importance:")
  - Bullet points under each section
  - Bold key information: dates, document names, notification numbers, section numbers, form names
- DO NOT mention:
  - context
  - sources
  - documents
  - knowledge base
  - steps
  - explanations about how you answered
- Write a clean, professional, well-structured answer with titles, subtitles, and bullet points.
- If information is missing, reply EXACTLY:
  "Information not available in the provided documents."

{body}

FINAL ANSWER:

"""


# ==========================================================
# BACKWARD-COMPATIBLE PROMPT CREATOR
# ==========================================================

def create_prompt(
    context: str,
    question: str,
    preferred_language: Optional[str] = None,
    chunks: Optional[List[Dict]] = None,
) -> str:
    """
    Backward-compatible wrapper.
    Uses provided context string if available, otherwise builds from chunks.
    """
    # If context is already built and valid, use it directly
    if context and context.strip() and context != "No specific context available from knowledge base.":
        body = f"""
CONTEXT (INTERNAL — DO NOT MENTION):
{context}

USER QUESTION:
{question}

"""
        return _wrap_enterprise_prompt(body)
    
    # If no valid context but chunks available, build from chunks
    if chunks:
        return build_rag_prompt(question, chunks)

    # Fallback: Use context string (even if empty) with enterprise prompt
    body = f"""
CONTEXT (INTERNAL — DO NOT MENTION):
{context or "No context available."}

USER QUESTION:
{question}

"""
    return _wrap_enterprise_prompt(body)


# ==========================================================
# ANSWER HIGHLIGHTING
# ==========================================================

def highlight_answer_with_keywords(
    answer: str,
    important_words: Optional[List[str]] = None
) -> str:
    """
    Safely highlight important keywords, titles, subtitles, and bullet points using **bold**
    without double-bolding.
    
    Formats:
    - Numbered titles/subtitles (1. Title:, 2. Title:)
    - Bullet points
    - Important keywords from query expansion
    """
    if not answer:
        return answer
    
    # First, highlight numbered titles/subtitles (1. Title:, 2. Title:, etc.)
    answer = re.sub(r'^(\d+\.\s+[^\n:]+:)\s*$', r'**\1**', answer, flags=re.MULTILINE)
    
    # Highlight titles ending with colon (likely section headings)
    answer = re.sub(r'^([A-Z][^\n]{2,60}):\s*$', r'**\1:**', answer, flags=re.MULTILINE)
    
    # Highlight common subtitle patterns (Key Details, Importance, Summary, etc.)
    subtitle_patterns = [
        r'^(Key\s+Details[^\n]*)',
        r'^(Importance[^\n]*)',
        r'^(Summary[^\n]*)',
        r'^(Conclusion[^\n]*)',
        r'^(Details[^\n]*)',
        r'^(Findings[^\n]*)',
        r'^(Analysis[^\n]*)',
        r'^(Explanation[^\n]*)',
    ]
    for pattern in subtitle_patterns:
        answer = re.sub(pattern, r'**\1**', answer, flags=re.MULTILINE | re.IGNORECASE)
    
    # Auto-highlight dates (e.g., "15th September, 2017", "28th June, 2017")
    answer = re.sub(r'(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s*,?\s+\d{4})', r'**\1**', answer, flags=re.IGNORECASE)
    
    # Auto-highlight notification numbers (e.g., "Notification No. 11", "Notification No. 4")
    answer = re.sub(r'(Notification\s+No\.?\s+\d+)', r'**\1**', answer, flags=re.IGNORECASE)
    
    # Auto-highlight document references (e.g., "Document 3", "Services.csv")
    answer = re.sub(r'(Document\s+\d+)', r'**\1**', answer, flags=re.IGNORECASE)
    answer = re.sub(r'([A-Z][a-zA-Z0-9_]+\.(?:csv|pdf|docx?|xlsx?))', r'**\1**', answer)
    
    # Auto-highlight section/rule references (e.g., "Section 16", "Rule 36")
    answer = re.sub(r'((?:Section|Rule|Chapter)\s+\d+[A-Z]?)', r'**\1**', answer, flags=re.IGNORECASE)
    
    # Then highlight important keywords (if provided)
    if important_words:
        words = sorted(
            {w.lower() for w in important_words if len(w) > 2},
            key=len,
            reverse=True
        )

        for word in words:
            # Skip if already bolded
            pattern = rf'(?<!\*)\b({re.escape(word)})\b(?!\*)'
            answer = re.sub(
                pattern,
                r'**\1**',
                answer,
                flags=re.IGNORECASE
            )

    return answer
