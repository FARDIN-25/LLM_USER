from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class QueryCreate(BaseModel):
    query_text: Optional[str] = None
    question: Optional[str] = None  # Alias for query_text
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    language: Optional[str] = None
    query_metadata: Optional[dict] = None
    
    def get_question_text(self) -> str:
        """Get question text (supports both 'question' and 'query_text' fields)."""
        return self.question or self.query_text or ""


class QueryOut(BaseModel):
    id: int
    query_text: str
    user_id: Optional[str]
    session_id: Optional[str]
    language: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ResponseCreate(BaseModel):
    query_id: int
    response_text: str
    retrieved_context_ids: Optional[List[int]] = None
    llm_model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    response_metadata: Optional[dict] = None


class ResponseOut(BaseModel):
    id: int
    query_id: int
    response_text: str
    created_at: datetime

    class Config:
        from_attributes = True

