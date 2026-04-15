"""
history search: GET /history/search.
Router and service live in history_search_service only.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db_service.database import get_db
from src.history_search_service.application.history_search_service import (
    search_sessions_history_suggestions,
)
from src.shared import schemas
from src.shared.security import get_current_user_email

router = APIRouter(tags=["History search"])


@router.get("/history/search", response_model=list[schemas.HistorySearchSuggestion])
def history_search(
    q: str = Query(..., min_length=1, max_length=200, description="Search term for title or query text"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Search chat history by session title or user query text.
    Returns suggestions with session_id, title, and preview for sidebar UI.
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return search_sessions_history_suggestions(db, current_user_id, q.strip(), limit=limit)
