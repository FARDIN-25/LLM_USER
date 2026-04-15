"""
Auto-tagging service: detect domain tags (GST, IT, Compliance, etc.) from query/response text.
Production-ready: keyword and pattern-based detection with configurable categories.
"""
import re
import logging
from typing import List

logger = logging.getLogger("fintax")

# Domain keywords and patterns for tag detection (production configurable via env if needed)
DOMAIN_KEYWORDS = {
    "GST": [
        r"\bGST\b", r"\bCGST\b", r"\bSGST\b", r"\bIGST\b", r"\bHSN\b", r"\bSAC\b",
        r"\binput\s+tax\s+credit\b", r"\boutput\s+tax\b", r"\bgoods\s+and\s+services\s+tax\b",
        r"\bGSTR\s*-\s*[123]\b", r"\breturn\s+filing\b", r"\breverse\s+charge\b",
        r"\bcomposition\s+scheme\b", r"\btax\s+invoice\b", r"\be-way\s+bill\b",
    ],
    "IT": [
        r"\bincome\s+tax\b", r"\bITR\b", r"\bTDS\b", r"\bTCS\b", r"\bSection\s+80\w*\b",
        r"\bSection\s+10\b", r"\bcapital\s+gains\b", r"\bdepreciation\b",
        r"\bPAN\b", r"\bAY\s*\d{4}", r"\bFY\s*\d{4}", r"\bassessment\s+year\b",
        r"\bdeduction\b", r"\bexemption\b", r"\bform\s+16\b", r"\bform\s+26AS\b",
    ],
    "Compliance": [
        r"\bcompliance\b", r"\bregulatory\b", r"\bact\s+and\s+rules\b", r"\bpenalty\b",
        r"\bnotice\b", r"\baudit\b", r"\bfine\b", r"\bstatutory\b", r"\bMCA\b", r"\bROC\b",
        r"\bcompanies\s+act\b", r"\bLLP\b",
    ],
    "ETC": [
        r"\bTDS\s+on\s+salary\b", r"\bPF\b", r"\bESI\b", r"\blabour\b", r"\bcontract\b",
        r"\bother\s+tax\b", r"\bmiscellaneous\b",
    ],
}


def detect_tags(text: str, max_tags: int = 5) -> List[str]:
    """
    Detect domain tags from text using keyword/pattern matching.
    Returns a list of tag strings (e.g. ["GST", "IT"]).
    """
    if not text or not isinstance(text, str):
        return []
    text_lower = text.lower()
    text_original = text
    tags = []
    for tag, patterns in DOMAIN_KEYWORDS.items():
        if len(tags) >= max_tags:
            break
        for pat in patterns:
            try:
                if re.search(pat, text_original, re.IGNORECASE) or (pat.replace(r"\b", "").replace("\\s+", " ").strip().lower() in text_lower):
                    if tag not in tags:
                        tags.append(tag)
                    break
            except re.error:
                continue
    return tags[:max_tags]


def tag_response(response_text: str, query_text: str = "", max_tags: int = 5) -> List[str]:
    """
    Combine response and query for tag detection. Prefer response content.
    """
    combined = f"{response_text or ''}\n{query_text or ''}"
    return detect_tags(combined, max_tags=max_tags)
