# src/followup_service/api/schemas.py
from pydantic import BaseModel

class FollowupRewriteRequest(BaseModel):
    user_id: str
    session_id: str
    question: str

class FollowupRewriteResponse(BaseModel):
    rewritten_question: str
    is_followup: bool
