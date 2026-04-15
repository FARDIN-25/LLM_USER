from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from sqlalchemy.orm import Session
import logging

from src.db_service.database import get_db
from src.db_service import models
from src.shared.security import get_current_user_email

logger = logging.getLogger("fintax")

router = APIRouter(tags=["Debug"])

@router.get("/api/debug/retrieval/latest")
async def get_latest_retrieval_debug(
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Returns the raw retrieval data (pre-reranking) for the user's most recent query.
    Used for the /debug-retrieval visualization page.
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Get the latest query response for this user
    latest_response = (
        db.query(models.QueryResponse)
        .join(models.UserQuery)
        .filter(models.UserQuery.user_id == current_user_id)
        .order_by(models.QueryResponse.created_at.desc())
        .first()
    )

    if not latest_response:
        return {"status": "error", "message": "No queries found for this user"}

    metadata = latest_response.response_metadata or {}
    raw_retrieval = metadata.get("raw_retrieval", [])

    return {
        "status": "success",
        "query_id": latest_response.query_id,
        "response_id": latest_response.id,
        "raw_retrieval": raw_retrieval,
        "timestamp": latest_response.created_at
    }

@router.get("/api/debug/retrieval/{query_id}")
async def get_query_retrieval_debug(
    query_id: int,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """Returns raw retrieval data for a specific query."""
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    response = db.query(models.QueryResponse).filter(models.QueryResponse.query_id == query_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")

    metadata = response.response_metadata or {}
    return {
        "status": "success",
        "query_id": query_id,
        "raw_retrieval": metadata.get("raw_retrieval", [])
    }
