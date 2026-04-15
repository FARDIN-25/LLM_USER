import re
import logging
from typing import Optional, List

import spacy

logger = logging.getLogger("fintax")

# --- Import Tax Vocabulary ---
try:
    from src.rag_service.application.query_expansion.tax_vocabulary import TAX_SYNONYMS
except ImportError:
    logger.warning("tax_vocabulary.py not found, using base keywords for follow-up detection.")
    TAX_SYNONYMS = {}

# Build a comprehensive set of standalone keywords from the tax vocabulary
_CORE_STANDALONE_KEYWORDS = {
    "gst", "gstr", "section", "income", "tax", "tds", "tcs", "itr", 
    "deduction", "exemption", "audit", "compliance", "return", "pan", "aadhar",
    "bhaaskar"
}

def _get_all_standalone_keywords():
    keywords = set(_CORE_STANDALONE_KEYWORDS)
    if isinstance(TAX_SYNONYMS, dict):
        for k, v in TAX_SYNONYMS.items():
            keywords.add(k.lower())
            if isinstance(v, list):
                for syn in v:
                    if isinstance(syn, str):
                        keywords.add(syn.lower())
    return keywords

STANDALONE_KEYWORDS_REGISTRY = _get_all_standalone_keywords()
# -----------------------------

_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load('en_core_web_sm')
        except Exception:
            _nlp = None
    return _nlp

class FollowupDetector:
    """
    Detects if a question is likely a follow-up question that needs context
    from previous interactions.
    """

    CONTEXTUAL_MARKERS = {
        "it", "its", "this", "that", "these", "those",
        "they", "them", "their",
        "he", "she", "his", "her",
        "types", "benefits", "examples",
        "advantages", "disadvantages",
        "difference", "limit", "exemption", "penalty",
        "requirement", "rule", "section"
    }
    
    # These should NOT trigger a follow-up on their own
    FIRST_PERSON_PRONOUNS = {"i", "me", "my", "mine", "we", "us", "our", "ours"}

    # Class attributes for standalone keywords
    _STANDALONE_CACHE = STANDALONE_KEYWORDS_REGISTRY

    PHRASE_MARKERS = [
        "how does it work",
        "why is it used",
        "who founded it",
        "how is it calculated"
    ]

    FOLLOWUP_PATTERNS = [
        r"^how\s+(does|do|did)\s+(it|this|that)",
        r"^why\s+(is|was)\s+(it|this|that)",
        r"^what\s+are\s+(its|their)",
        r"^what\s+about",
        r"^and\s",
        r"^then\s"
    ]

    @classmethod
    def is_followup(cls, question: str, previous_query: Optional[str] = None) -> bool:
        if not question:
            return False

        question_lower = question.lower()
        
        # 0. PERSONAL INTENT BYPASS (Enterprise-safe)
        # If the user is asking about themselves or greeting, NEVER treat as a follow-up.
        personal_markers = ["my name", "who am i", "my pan", "my tan", "my regime", "my profile", "my status", "tell me about myself", "hi", "hello", "hey", "vanakkam"]
        if any(marker in question_lower for marker in personal_markers):
            return False

        nlp = get_nlp()
        
        if nlp:
            doc = nlp(question_lower)
            
            # The query contains pronouns referring to previous context
            for token in doc:
                if token.pos_ == "PRON" and token.text.lower() not in cls.FIRST_PERSON_PRONOUNS:
                    return True
                    
            # The query shares named entities with the previous query
            if previous_query is not None:
                prev_doc = nlp(previous_query.lower())
                prev_ents = {ent.text for ent in prev_doc.ents if ent.text.strip()}
                curr_ents = {ent.text for ent in doc.ents if ent.text.strip()}
                if prev_ents.intersection(curr_ents):
                    return True

        # Phrase detection
        for phrase in cls.PHRASE_MARKERS:
            if phrase in question_lower:
                return True

        # Pattern detection
        for pattern in cls.FOLLOWUP_PATTERNS:
            if re.search(pattern, question_lower):
                return True

        # Tokenization fallback
        tokens = set(re.findall(r"\b[a-zA-Z]{2,}\b", question_lower))

        # Context markers (excluding first-person)
        if tokens.intersection(cls.CONTEXTUAL_MARKERS - cls.FIRST_PERSON_PRONOUNS):
            return True

        # Short question heuristic: Only if it lacks standalone keywords
        has_standalone = False
        for kw in cls._STANDALONE_CACHE:
            if kw in question_lower:
                has_standalone = True
                break
                
        if len(tokens) <= 3 and not has_standalone:
            return True

        return False