import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.db_service.database import get_db
from src.db_service import crud
from src.shared.security import get_current_user_email
from src.shared import schemas
from src.category_service.application.category_service import normalize_category

logger = logging.getLogger("fintax")

router = APIRouter(tags=["Category"])


@router.get("/queries/category/{category}", response_model=List[schemas.QueryOut])
def get_queries_by_category(
    category: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Filter user queries by detected category for the current user.
    This powers UI filtering (ChatGPT-style topic buckets) without new tables.
    """
    if not current_user_id:
        # Keep consistent with existing auth-gated history endpoints
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use cookie or Authorization: Bearer token.",
        )

    normalized = normalize_category(category)
    return crud.get_queries_by_user_and_category(db, current_user_id, normalized, limit=limit)

