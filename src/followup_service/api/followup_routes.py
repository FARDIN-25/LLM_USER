# src/followup_service/api/followup_routes.py
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from src.db_service.database import get_db
from sqlalchemy.orm import Session

from src.shared.security import get_current_user_email
from src.followup_service.api import schemas
from src.followup_service.application.followup_pipeline import FollowupPipeline

logger = logging.getLogger("fintax")
router = APIRouter(tags=["Follow-up"])

@router.post("/followup/rewrite", response_model=schemas.FollowupRewriteResponse)
async def rewrite_followup(
    payload: schemas.FollowupRewriteRequest,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    API endpoint to explicitly test and rewrite follow-up questions.
    Expects user_id from the payload, but requires a valid session to execute.
    """
    if not current_user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use cookie or Authorization: Bearer token."
        )
        
    # Verify that the user owns the data or matches payload (payload requirement from prompt)
    if current_user_id != payload.user_id:
        raise HTTPException(
            status_code=403,
            detail="Mismatch between authenticated user and request user_id"
        )
        
    try:
        rewritten, is_followup = FollowupPipeline.process(
            db=db,
            session_id=payload.session_id,
            question=payload.question
        )
        
        return schemas.FollowupRewriteResponse(
            rewritten_question=rewritten,
            is_followup=is_followup
        )
    except Exception as e:
        logger.error(f"Followup rewrite error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
