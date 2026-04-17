from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Tuple

Route = Literal["lookup", "semantic", "ambiguous"]


@dataclass(frozen=True)
class RoutingResult:
    route: Route
    confidence: int
    lookup_score: int
    semantic_score: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "route": self.route,
            "confidence": self.confidence,
            "lookup_score": self.lookup_score,
            "semantic_score": self.semantic_score,
        }


LOOKUP_KEYWORDS: Tuple[str, ...] = ("what is", "who is", "define", "meaning", "full form")
SEMANTIC_KEYWORDS: Tuple[str, ...] = ("explain", "why", "how", "compare", "impact", "analysis")
DOC_HINTS: Tuple[str, ...] = (".pdf", ".doc")


def _preprocess(query: str) -> str:
    # Requirements: lowercase + strip spaces
    return query.lower().strip()


def _word_count(text: str) -> int:
    # Treat any whitespace as a delimiter; ignore repeated spaces.
    return len([w for w in text.split() if w])


def _contains_any_substring(text: str, needles: Tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _contains_number(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _score_query(text: str) -> Tuple[int, int]:
    lookup_score = 0
    semantic_score = 0

    # A. Query length
    if _word_count(text) <= 4:
        lookup_score += 1
    else:
        semantic_score += 1

    # B. Lookup keywords
    if _contains_any_substring(text, LOOKUP_KEYWORDS):
        lookup_score += 2

    # C. Semantic keywords
    if _contains_any_substring(text, SEMANTIC_KEYWORDS):
        semantic_score += 2

    # D. Entity detection
    if _contains_number(text):
        lookup_score += 1
    if _contains_any_substring(text, DOC_HINTS):
        lookup_score += 2

    return lookup_score, semantic_score


def _decide_route(lookup_score: int, semantic_score: int) -> Route:
    if lookup_score > semantic_score:
        return "lookup"
    if semantic_score > lookup_score:
        return "semantic"
    return "ambiguous"


def classify_query(query: str) -> dict:
    """
    Classify a query into a retrieval route using scoring-based signals.

    Routes:
    - lookup: best served by precise keyword/FTS lookup.
    - semantic: best served by semantic/hybrid retrieval.
    - ambiguous: use both (Hybrid + FTS) and merge.
    """
    q = _preprocess(query)
    lookup_score, semantic_score = _score_query(q)
    route = _decide_route(lookup_score, semantic_score)
    confidence = abs(lookup_score - semantic_score)

    return RoutingResult(
        route=route,
        confidence=confidence,
        lookup_score=lookup_score,
        semantic_score=semantic_score,
    ).as_dict()

