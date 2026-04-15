"""
Folder assignment service: assign uploads/chunks to GST, IT, ETC based on content or explicit choice.
Production-ready: explicit assignment takes precedence; otherwise heuristic from filename/content.
"""
import re
import logging
from typing import Optional, List

logger = logging.getLogger("fintax")

FOLDER_VALUES = ("GST", "IT", "ETC")

# Heuristics: keywords that suggest a folder
FOLDER_KEYWORDS = {
    "GST": ["gst", "cgst", "sgst", "igst", "hsn", "sac", "gstr", "tax invoice", "eway"],
    "IT": ["income tax", "itr", "tds", "tcs", "section 80", "pan", "form 16", "capital gain", "assessment year"],
    "ETC": ["labour", "pf", "esi", "contract", "misc", "other"],
}


def assign_folder(
    folder_assignment: Optional[str] = None,
    file_path: Optional[str] = None,
    file_type: Optional[str] = None,
    content_preview: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Resolve folder_assignment: if provided and valid, return it; else infer from path/type/content/tags.
    Returns one of 'GST', 'IT', 'ETC' or None.
    """
    if folder_assignment and str(folder_assignment).strip().upper() in FOLDER_VALUES:
        return str(folder_assignment).strip().upper()

    combined = " ".join(
        filter(
            None,
            [
                (file_path or "").lower(),
                (file_type or "").lower(),
                (content_preview or "")[:2000].lower(),
                " ".join(tags or []).lower(),
            ],
        )
    )
    if not combined:
        return None

    scores = {f: 0 for f in FOLDER_VALUES}
    for folder, keywords in FOLDER_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[folder] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def extract_tags_from_content(content: Optional[str], max_tags: int = 10) -> List[str]:
    """
    Extract simple tags from content (e.g. section numbers, act names).
    Used during document processing for upload tag extraction.
    """
    if not content or max_tags <= 0:
        return []
    tags = []
    # Section-like: Section 80C, Section 10, etc.
    for m in re.finditer(r"Section\s+(\d+[A-Za-z]?)", content, re.IGNORECASE):
        tag = f"Section_{m.group(1)}"
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= max_tags:
            break
    for m in re.finditer(r"\b(GST|ITR|TDS|TCS|CGST|SGST|IGST|HSN|SAC)\b", content):
        t = m.group(1).upper()
        if t not in tags:
            tags.append(t)
        if len(tags) >= max_tags:
            break
    return tags[:max_tags]
