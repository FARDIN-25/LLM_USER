"""Minimal query expansion stub for development/testing.

This module provides `expand_query` so the application can enable
`QUERY_EXPANSION_AVAILABLE` without requiring the production expansion
implementation. The function returns the input query unchanged.
"""

from typing import List


def expand_query(query: str) -> str:
    """Return an expanded query string.

    This minimal stub returns the original query unchanged. Replace
    with a real implementation to enable actual expansion.
    """
    return query


def expand_query_terms(query: str) -> List[str]:
    """Optional helper: split query into simple term list."""
    if not query:
        return []
    return [t.strip() for t in query.split() if t.strip()]
