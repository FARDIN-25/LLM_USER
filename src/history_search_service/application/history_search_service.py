"""
History search service: sidebar search.
All search logic lives here; router in api/routes.py calls this only.
"""
from typing import List

from sqlalchemy import desc, or_, String, select
from sqlalchemy.orm import Session

from src.db_service import models


def search_sessions_history_suggestions(
    db: Session, user_id: str, search_term: str, limit: int = 10
) -> List[dict]:
    """
    Search chat history by session title (history JSON) or user_queries.query_text.
    Returns list of {session_id, title, preview} ordered by session updated_at DESC.
    """
    if not (search_term or "").strip():
        return []
    pattern = f"%{(search_term or '').strip()}%"

    # Sessions whose title (in history JSON) matches
    title_match = models.ChatSession.history["title"].cast(String).ilike(pattern)
    # Session IDs that have at least one query matching the search term
    subq = (
        db.query(models.UserQuery.session_id)
        .filter(
            models.UserQuery.user_id == user_id,
            models.UserQuery.session_id.isnot(None),
            models.UserQuery.query_text.ilike(pattern),
        )
        .distinct()
        .subquery()
    )
    sessions = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.user_id == user_id,
            or_(title_match, models.ChatSession.session_id.in_(select(subq.c.session_id))),
        )
        .order_by(desc(models.ChatSession.updated_at))
        .limit(limit)
        .all()
    )
    if not sessions:
        return []

    session_ids = [s.session_id for s in sessions]
    # Latest query text per session for preview
    latest_queries = (
        db.query(models.UserQuery.session_id, models.UserQuery.query_text)
        .filter(models.UserQuery.session_id.in_(session_ids))
        .order_by(desc(models.UserQuery.created_at))
        .all()
    )
    preview_map = {}
    for sid, qtext in latest_queries:
        if sid not in preview_map:
            preview_map[sid] = (qtext or "")[:120].strip()

    def _title(sess: models.ChatSession) -> str:
        h = sess.history if isinstance(sess.history, dict) else {}
        return (h.get("title") or h.get("first_question") or "New chat") or "New chat"

    return [
        {
            "session_id": s.session_id,
            "title": _title(s),
            "preview": preview_map.get(s.session_id, ""),
        }
        for s in sessions
    ]
