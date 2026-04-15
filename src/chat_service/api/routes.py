"""
Chat and Query routes - RAG pipeline endpoints.
Refactored to use ChatService (Controller Pattern).
"""
import logging
import uuid
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from src.db_service.database import get_db
from src.db_service import crud, models
from src.shared import schemas
from src.shared.security import get_current_user_email
from src.chat_service.application.chat_service import ChatService

logger = logging.getLogger("fintax")

router = APIRouter(tags=["Chat"])

# Authenticated email is used as user_id app-wide (DB, sessions). Injected via get_current_user_email.

# Initialize embedding model (shared across requests)
# TODO: Move this to a dedicated ModelService or Singleton to avoid circular imports
try:
    from sentence_transformers import SentenceTransformer
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    logger.info("Embedding model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load embedding model — vector search will be disabled: {e}")
    embedding_model = None


# the chat creation point
@router.post("/chat")
async def chat(
    payload: dict,
    db: Session = Depends(get_db),
    reranking_enabled: bool = Query(True),
    reranker_type: str = Query(None, description="Reranker type: cross-encoder, cohere, bge, or llm"),
    limit: int = Query(5),
    hybrid_retrieval_enabled: bool = Query(True, description="Enable hybrid retrieval (dense + sparse BM25)"),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Chat endpoint - KB + LLM = Answer (RAG Pipeline)
    Fintax-style session: if payload.session_id sent and valid → continue that session;
    else create new. Delegates to ChatService.
    """
    start_time = time.time()
    try:
        question = payload.get("question") or payload.get("query_text")
        if not question:
            raise HTTPException(status_code=400, detail="Missing 'question' field")

        logger.info(f"📨 Chat request: {question[:100]}")

        if not current_user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Use cookie or Authorization: Bearer token.",
            )

        # Fintax-style: frontend sends session_id (from sessionStorage) to continue session.
        # If provided and valid → continue; else create new session.
        is_temporary = payload.get("is_temporary", False)
        user_id = current_user_id
        session_id_from_frontend = payload.get("session_id") or None

        query_create = schemas.QueryCreate(
            query_text=question,
            language=payload.get("language"),
            session_id=session_id_from_frontend,
            is_temporary=is_temporary,
            user_id=user_id,
        )

        service = ChatService(db, embedding_model)
        result = await service.process_chat(
            payload=query_create,
            reranking_enabled=reranking_enabled,
            reranker_type=reranker_type,
            limit=limit,
            hybrid_retrieval_enabled=hybrid_retrieval_enabled,
            query_expansion_enabled=True  # Default for chat endpoint
        )

        # Return format expected by frontend (session_id from active session)
        return {
            "status": "success",
            "answer": result["answer"],
            "reply": result["answer"],
            "important_words": result.get("important_words", []),
            "language_response": result.get("language_response"),
            "tags": result.get("tags", []),
            "query_id": result.get("query_id"),
            "response_id": result.get("response_id"),
            "message_id": result.get("message_id"),
            "session_id": result.get("session_id"),
            "category": result.get("category"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/new")
async def new_chat(
    payload: dict = {},
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Create a new session and return new session_id. Previous history is not removed (no soft delete).
    Router delegates to session_service; no DB logic here.
    """
    try:
        from src.auth_service.application.session_service import create_new_session

        if not current_user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Use cookie or Authorization: Bearer token.",
            )

        new_session = create_new_session(db, current_user_id)

        return {
            "status": "success",
            "session_id": new_session.session_id,
            "message": "New chat session created"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ New chat session creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_rag(
    payload: schemas.QueryCreate,
    db: Session = Depends(get_db),
    query_expansion_enabled: bool = Query(True, description="Enable query expansion (default: True)"),
    expansion_strategy: str = Query(None, description="Expansion strategy: static, llm, hybrid, module_wise, or token_optimized"),
    reranking_enabled: bool = Query(True),
    hybrid_retrieval_enabled: bool = Query(True),
    reranker_type: str = Query(None, description="Reranker type: cross-encoder, cohere, bge, or llm"),
    limit: int = Query(5)
):
    """
    Full RAG Pipeline Endpoint
    Delegates to ChatService.
    """
    try:
        service = ChatService(db, embedding_model)
        return await service.process_chat(
            payload=payload,
            reranking_enabled=reranking_enabled,
            reranker_type=reranker_type,
            limit=limit,
            hybrid_retrieval_enabled=hybrid_retrieval_enabled,
            query_expansion_enabled=query_expansion_enabled,
            expansion_strategy=expansion_strategy
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Query RAG failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Favourites (messages with react != "no_react")
# =============================================================================

@router.get("/favourites", response_model=list[schemas.ChatMessageOut])
def get_user_favourites(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Get all favourite messages for the current user (across all sessions).
    Requires user_id in X-User-ID header or authorization token.
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Use cookie or Authorization: Bearer token.")

    return crud.get_favourites_by_user(db, current_user_id, limit=limit)


# =============================================================================
# Session history (Fintax-style sidebar)
# =============================================================================

@router.get("/sessions/history")
def get_sessions_history(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Return sessions for the current user (exclude deleted), sorted latest first.
    Each session includes session_id, title, updated_at, created_at for sidebar display.
    Requires authenticated user (JWT email as user_id).
    """
    if not current_user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use cookie or Authorization: Bearer token.",
        )
    user_id = current_user_id
    service = ChatService(db, embedding_model)
    return service.get_user_history(user_id, limit=limit)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Delete a chat session and all its messages.
    Verifies session belongs to current user.
    """
    if not current_user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    service = ChatService(db, embedding_model)
    result = service.delete_session(session_id, current_user_id)
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Session not found in database")
    if result == "not_owned":
        raise HTTPException(status_code=403, detail="You do not have permission to delete this session")
    if not result:
        raise HTTPException(status_code=500, detail="Database error occurred during deletion")

    return {"status": "success", "message": "Session deleted successfully"}


@router.patch("/sessions/{session_id}/history")
def update_session_history_title(
    session_id: str,
    data: schemas.SessionHistoryTitleUpdate,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Rename chat title for sidebar. Saves to chat_sessions.history.title in database.
    Verifies session belongs to current user.
    """
    if not current_user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use cookie or Authorization: Bearer token.",
        )
    user_id = current_user_id
    session = crud.get_chat_session_by_session_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only rename your own sessions.")
    service = ChatService(db, embedding_model)
    if not service.update_session_title(session_id, data.title, user_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "session_id": session_id, "title": data.title.strip()[:200]}


@router.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Return full conversation for a session: join user_queries + query_responses, order by time ASC.
    Verifies session belongs to current user.
    """
    if not current_user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use cookie or Authorization: Bearer token.",
        )
    user_id = current_user_id
    session = crud.get_chat_session_by_session_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only access your own sessions.")
    service = ChatService(db, embedding_model)
    return service.get_session_messages(session_id, limit=limit)


@router.get("/sessions/{session_id}/favourites", response_model=list[schemas.ChatMessageOut])
def get_session_favourites(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Get favourite messages for a specific session.
    Requires authentication (cookie or Authorization: Bearer).
    Verifies that the session belongs to the user.
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Use cookie or Authorization: Bearer token.")

    # Verify session ownership
    session = crud.get_chat_session_by_session_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only access your own sessions.")

    return crud.get_chat_messages_by_session(db, session_id, favourites_only=True, limit=limit)


@router.put("/sessions/{session_id}/metadata")
def update_session_metadata(
    session_id: str,
    data: schemas.ChatSessionMetadataUpdate,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Update rich user profile metadata for a session (deep merge).
    Requires authentication (cookie or Authorization: Bearer).
    Verifies that the session belongs to the user.
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Use cookie or Authorization: Bearer token.")

    # Verify session ownership
    session = crud.get_chat_session_by_session_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only access your own sessions.")

    updated_session = crud.update_session_metadata(db, session_id, data.metadata_)
    if not updated_session:
        raise HTTPException(status_code=500, detail="Failed to update session metadata")

    return {"status": "success", "session_id": session_id, "metadata": updated_session.session_metadata}


# =============================================================================
# Single emoji reaction (POST /chat/react, GET /chat/react/{message_id})
# =============================================================================

# =============================================================================
# Edit question & regenerate answer (Fintax-style; same rows, no new tables)
# =============================================================================

@router.post("/chat/edit")
async def chat_edit(
    data: schemas.ChatEditBody,
    db: Session = Depends(get_db),
    reranking_enabled: bool = Query(True),
    reranker_type: str = Query(None),
    limit: int = Query(5),
    hybrid_retrieval_enabled: bool = Query(True),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Edit user question and regenerate answer. Flow: edit_query (commit) -> hide_future_messages (commit)
    -> regenerate_response (update same query_responses row). No new tables; chat_messages links unchanged.
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    service = ChatService(db, embedding_model)
    # 1. Update user_queries row: query_text + metadata.edited = true; commit in crud
    query_row = service.edit_query(data.query_id, data.new_text.strip(), current_user_id)
    session_id = (query_row and query_row.session_id) or ""
    if not session_id:
        raise HTTPException(status_code=400, detail="Query has no session")
    # 2. Mark all messages after this query in session as hidden (no physical delete)
    service.hide_future_messages(session_id, data.query_id, current_user_id)
    # 3. Regenerate answer for edited query; update existing query_responses row
    result = await service.regenerate_response(
        data.query_id,
        reranking_enabled=reranking_enabled,
        reranker_type=reranker_type,
        limit=limit,
        hybrid_retrieval_enabled=hybrid_retrieval_enabled,
        query_expansion_enabled=True,
    )
    return {
        "status": "success",
        "answer": result["answer"],
        "query_text": data.new_text.strip(),
        "query_id": result["query_id"],
        "response_id": result["response_id"],
        "edited": True,
    }


@router.post("/chat/regenerate")
async def chat_regenerate(
    data: schemas.ChatRegenerateBody,
    db: Session = Depends(get_db),
    reranking_enabled: bool = Query(True),
    reranker_type: str = Query(None),
    limit: int = Query(5),
    hybrid_retrieval_enabled: bool = Query(True),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Regenerate answer for the same question (no edit). Updates existing query_responses row;
    chat_messages and user_queries unchanged. Router delegates to service (no DB logic here).
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    # Verify query belongs to user's session
    query_row = crud.get_query_by_id(db, data.query_id)
    if not query_row:
        raise HTTPException(status_code=404, detail="Query not found")
    session = crud.get_chat_session_by_session_id(db, query_row.session_id or "")
    if not session or session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only regenerate your own messages")
    service = ChatService(db, embedding_model)
    result = await service.regenerate_response(
        data.query_id,
        reranking_enabled=reranking_enabled,
        reranker_type=reranker_type,
        limit=limit,
        hybrid_retrieval_enabled=hybrid_retrieval_enabled,
        query_expansion_enabled=True,
    )
    return {
        "status": "success",
        "answer": result["answer"],
        "query_id": result["query_id"],
        "response_id": result["response_id"],
    }


@router.post("/chat/react", response_model=schemas.ChatMessageOut)
def set_reaction(
    data: schemas.ReactSetBody,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Set the single emoji reaction for a message. Only for messages in the user's session.
    Empty emoji → store "no_react". Router delegates to service (no DB logic here).
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Use cookie or Authorization: Bearer token.")
    if not crud.verify_message_ownership(db, data.message_id, current_user_id):
        raise HTTPException(status_code=403, detail="You can only react to your own messages.")
    service = ChatService(db, embedding_model)
    return service.set_message_reaction(data.message_id, current_user_id, data.emoji)


@router.get("/chat/react/{message_id}", response_model=schemas.ReactGetResponse)
def get_reaction(
    message_id: int,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Depends(get_current_user_email),
):
    """
    Return the stored emoji for the message (or "no_react").
    Router delegates to service (no DB logic here).
    """
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Use cookie or Authorization: Bearer token.")
    if not crud.verify_message_ownership(db, message_id, current_user_id):
        raise HTTPException(status_code=403, detail="You can only view reactions for your own messages.")
    service = ChatService(db, embedding_model)
    emoji = service.get_message_reaction(message_id)
    return schemas.ReactGetResponse(emoji=emoji)