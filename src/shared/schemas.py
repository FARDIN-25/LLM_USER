from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# =============================================================================
# QUERY / RESPONSE (existing + Phase 2 updates)
# =============================================================================

class QueryRequest(BaseModel):
    question: str
    expansion_strategy: Optional[str] = None


class QueryCreate(BaseModel):
    query_text: Optional[str] = None
    question: Optional[str] = None  # Alias for query_text
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    is_temporary: Optional[bool] = False
    language: Optional[str] = None
    query_metadata: Optional[dict] = None
    # Automatic topic clustering (computed server-side before retrieval)
    category: Optional[str] = None

    def get_question_text(self) -> str:
        """Get question text (supports both 'question' and 'query_text' fields)."""
        return self.question or self.query_text or ""


class QueryOut(BaseModel):
    id: int
    query_text: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    is_temporary: Optional[bool] = False
    language: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ResponseCreate(BaseModel):
    query_id: int
    response_text: str
    retrieved_context_ids: Optional[List[str]] = None
    llm_model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    response_metadata: Optional[dict] = None
    tags: Optional[List[str]] = None
    language_response: Optional[Dict[str, str]] = None  # e.g. {"english": "...", "tamil": "..."}


class ResponseOut(BaseModel):
    id: int
    query_id: Optional[int] = None
    response_text: str
    tags: Optional[List[str]] = None
    language_response: Optional[Dict[str, str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# LEGACY SESSION (existing - sessions table)
# =============================================================================

class SessionIn(BaseModel):
    session_id: str


class SessionOut(BaseModel):
    session_id: str
    created_at: str
    last_activity_at: str
    query_count: int


# =============================================================================
# PHASE 2: ChatSession
# =============================================================================

class ChatSessionCreate(BaseModel):
    user_id: str
    session_id: Optional[str] = None  # If not provided, API can generate UUID


class ChatSessionOut(BaseModel):
    id: int
    user_id: str
    session_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionUpdate(BaseModel):
    """Reserved for future session updates."""


class ChatSessionUpdateWithId(BaseModel):
    """For PATCH /api/sessions (session_id in body)."""
    session_id: str


class SessionHistoryTitleUpdate(BaseModel):
    """Body for PATCH /sessions/{session_id}/history - rename chat title in sidebar."""
    title: str = Field(..., min_length=1, max_length=200)


class ChatSessionMetadataUpdate(BaseModel):
    """Body for PUT /session/{session_id}/metadata - update rich user profile metadata."""
    metadata_: Dict[str, Any] = Field(..., alias="metadata")


class HistorySearchSuggestion(BaseModel):
    """One suggestion item for ChatGPT-style sidebar history search."""
    session_id: str
    title: str
    preview: Optional[str] = None


# =============================================================================
# PHASE 2: ChatMessage
# =============================================================================

class ChatMessageCreate(BaseModel):
    session_id: str
    query_id: int
    response_id: int
    react: str = "no_react"  # Single emoji; "no_react" = none
    tags: Optional[List[str]] = None
    feedback: Optional[str] = Field(None, pattern="^(up|down)$")


class ChatMessageOut(BaseModel):
    id: int
    session_id: str
    query_id: int
    response_id: int
    react: str  # Stored emoji or "no_react"
    tags: Optional[List[str]] = None
    feedback: Optional[str] = None
    created_at: datetime

    @field_validator("react", mode="before")
    @classmethod
    def normalize_react(cls, v: Any) -> str:
        """Never expose legacy 'true'/'false'; use 'no_react'."""
        if v is None or (isinstance(v, str) and v.strip().lower() in ("true", "false")):
            return "no_react"
        if isinstance(v, bool):
            return "no_react"
        return (v if isinstance(v, str) else str(v)).strip() or "no_react"

    class Config:
        from_attributes = True


class ChatMessageUpdate(BaseModel):
    react: Optional[str] = None  # Emoji string or empty → "no_react"
    tags: Optional[List[str]] = None
    feedback: Optional[str] = Field(None, pattern="^(up|down)$")


# =============================================================================
# PHASE 2: Subscription
# =============================================================================

class SubscriptionCreate(BaseModel):
    user_id: str
    plan_type: str = "Free"  # Free, Pro, Enterprise
    features: Optional[Dict[str, Any]] = None
    usage_limits: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class SubscriptionOut(BaseModel):
    id: int
    user_id: str
    plan_type: str
    features: Optional[Dict[str, Any]] = None
    usage_limits: Optional[Dict[str, Any]] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionUpdate(BaseModel):
    plan_type: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    usage_limits: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


# =============================================================================
# PHASE 2: FileUpload
# =============================================================================

class FileUploadCreate(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    file_path: str
    file_type: Optional[str] = None
    tags: Optional[str] = None  # Category/tags: GST, IT, ETC


class FileUploadOut(BaseModel):
    id: int
    user_id: str
    session_id: Optional[str] = None
    file_path: str
    file_type: Optional[str] = None
    tags: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class FileUploadUpdate(BaseModel):
    tags: Optional[str] = None


# =============================================================================
# Single emoji reaction (chat_messages.react)
# =============================================================================

class ChatEditBody(BaseModel):
    """Body for POST /chat/edit - edit question and regenerate answer."""
    query_id: int
    new_text: str = Field(..., min_length=1)


class ChatRegenerateBody(BaseModel):
    """Body for POST /chat/regenerate - regenerate answer for same question (no edit)."""
    query_id: int


class ReactSetBody(BaseModel):
    """Body for POST /chat/react."""
    message_id: int
    emoji: str = ""  # Empty → store "no_react"


class ReactGetResponse(BaseModel):
    """Response for GET /chat/react/{message_id}."""
    emoji: str  # Stored emoji or "no_react"
