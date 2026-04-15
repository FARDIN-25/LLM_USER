from sqlalchemy.orm import Session
from . import models
from src.shared import schemas
from datetime import datetime, timedelta
from sqlalchemy import desc
from typing import List, Optional
import logging


logger = logging.getLogger("fintax")
# =============================================================================
# UserQuery
# =============================================================================

def create_query(db: Session, query: schemas.QueryCreate):
    """Create a new user query. Safe transaction: rollback on failure so session stays valid."""
    query_text = query.get_question_text() if hasattr(query, "get_question_text") else (query.query_text or query.question or "")
    # Ensure category is never None so DB stores the detected value (GST/INCOME_TAX/TDS/ROC/GENERAL)
    raw_cat = getattr(query, "category", None)
    category = (raw_cat if isinstance(raw_cat, str) and raw_cat.strip() else None) or "GENERAL"
    db_query = models.UserQuery(
        query_text=query_text,
        user_id=query.user_id,
        session_id=query.session_id,
        is_temporary=query.is_temporary if query.is_temporary is not None else False,
        language=query.language,
        query_metadata=query.query_metadata,
        category=category,
    )
    try:
        db.add(db_query)
        db.commit()
        db.refresh(db_query)
        return db_query
    except Exception as e:
        db.rollback()
        logger.error("❌ UserQuery insert failed: %s", e, exc_info=True)
        raise


def get_recent_queries(db: Session, hours: int = 24, limit: int = 100):
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(models.UserQuery)
        .filter(models.UserQuery.created_at >= cutoff_time)
        .order_by(desc(models.UserQuery.created_at))
        .limit(limit)
        .all()
    )


def get_first_query_in_session(db: Session, session_id: str) -> Optional[models.UserQuery]:
    """Return the earliest user query in a session (by created_at ASC). Used for title derivation."""
    return (
        db.query(models.UserQuery)
        .filter(models.UserQuery.session_id == session_id)
        .order_by(models.UserQuery.created_at.asc())
        .first()
    )


def update_query_metadata(db: Session, query_id: int, metadata_update: dict) -> Optional[models.UserQuery]:
    """Merge metadata_update into the query's query_metadata (e.g. store session_title). No schema change."""
    q = db.query(models.UserQuery).filter(models.UserQuery.id == query_id).first()
    if not q:
        return None
    current = q.query_metadata or {}
    if not isinstance(current, dict):
        current = {}
    current.update(metadata_update)
    q.query_metadata = current
    db.commit()
    db.refresh(q)
    return q


def search_queries(db: Session, search_term: str, limit: int = 50):
    return (
        db.query(models.UserQuery)
        .filter(models.UserQuery.query_text.ilike(f"%{search_term}%"))
        .limit(limit)
        .all()
    )


def get_query_by_id(db: Session, query_id: int) -> Optional[models.UserQuery]:
    return db.query(models.UserQuery).filter(models.UserQuery.id == query_id).first()


def update_query_text_and_metadata(
    db: Session, query_id: int, new_text: str, metadata_merge: Optional[dict] = None
) -> Optional[models.UserQuery]:
    """
    Update query_text and merge into query_metadata (e.g. {"edited": True}).
    Used for edit-question flow; does not create new rows.
    """
    q = db.query(models.UserQuery).filter(models.UserQuery.id == query_id).first()
    if not q:
        return None
    q.query_text = new_text
    # Keep category consistent when the user edits their question (inline fallback if import fails)
    try:
        from src.category_service.application.category_service import detect_category
        q.category = detect_category(new_text)
    except Exception:
        t = (new_text or "").lower()
        if "gst" in t:
            q.category = "GST"
        elif ("income tax" in t) or ("itr" in t) or ("tax rebate" in t):
            q.category = "INCOME_TAX"
        elif "tds" in t:
            q.category = "TDS"
        elif ("roc" in t) or ("company filing" in t) or ("roc annual filing" in t):
            q.category = "ROC"
        else:
            q.category = "GENERAL"
    current = q.query_metadata or {}
    if not isinstance(current, dict):
        current = {}
    if metadata_merge:
        current.update(metadata_merge)
    q.query_metadata = current
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(q)
    return q


def get_queries_by_user_and_category(
    db: Session, user_id: str, category: str, limit: int = 100
) -> List[models.UserQuery]:
    """Return latest queries for a user filtered by category (topic bucket)."""
    return (
        db.query(models.UserQuery)
        .filter(models.UserQuery.user_id == user_id, models.UserQuery.category == category)
        .order_by(desc(models.UserQuery.created_at))
        .limit(limit)
        .all()
    )


# =============================================================================
# QueryResponse
# =============================================================================

def _safe_context_ids(ids) -> list:
    """Ensure context IDs are strings for ARRAY(String) storage (e.g., 'docs_123')."""
    if not ids:
        return []
    # If it's already a list of strings, return as is (stripped)
    return [str(x).strip() for x in ids if x is not None]


def get_unified_chunk(db: Session, unified_id: str) -> Optional[dict]:
    """
    Resolve a chunk from either docs_chunks or book_chunks based on prefix.
    Prefixes: 'docs_' or 'book_'
    """
    if not isinstance(unified_id, str):
        logger.warning(f"⚠️ Invalid unified_id type: {type(unified_id)}")
        return None

    try:
        if unified_id.startswith("docs_"):
            real_id = int(unified_id.replace("docs_", ""))
            chunk = db.query(models.DocsChunk).filter(models.DocsChunk.id == real_id).first()
            if chunk:
                return {
                    "id": unified_id,
                    "text": chunk.chunk_text,
                    "content": chunk.chunk_text,
                    "metadata": {
                        **(dict(chunk.chunk_metadata) if chunk.chunk_metadata else {}),
                        "domain": chunk.domain,
                        "source_file": chunk.source_file,
                        "source": "docs"
                    }
                }
        elif unified_id.startswith("book_"):
            real_id = int(unified_id.replace("book_", ""))
            chunk = db.query(models.BookChunk).filter(models.BookChunk.id == real_id).first()
            if chunk:
                return {
                    "id": unified_id,
                    "text": chunk.chunk_text,
                    "content": chunk.chunk_text,
                    "metadata": {
                        **(dict(chunk.chunk_metadata) if chunk.chunk_metadata else {}),
                        "source_file": chunk.source_file,
                        "source": "book"
                    }
                }
        pass
    except (ValueError, TypeError) as e:
        logger.error(f"❌ Failed to parse unified ID {unified_id}: {e}")
    
    return None


def create_response(db: Session, response: schemas.ResponseCreate):
    """Create a new query response with safe transaction handling. No limit — every call inserts a new row."""
    metadata = dict(response.response_metadata or {})
    if response.prompt_tokens is not None or response.completion_tokens is not None:
        metadata["prompt_tokens"] = response.prompt_tokens or 0
        metadata["completion_tokens"] = response.completion_tokens or 0
        metadata["total_tokens"] = (
            response.total_tokens
            or (response.prompt_tokens or 0) + (response.completion_tokens or 0)
        )

    # Ensure types match DB (String[], JSON); avoid insert failure on 2nd/3rd request
    context_ids = _safe_context_ids(response.retrieved_context_ids or [])
    tags = list(response.tags) if response.tags else []
    lang_resp = response.language_response if isinstance(response.language_response, dict) else {}

    try:
        db_response = models.QueryResponse(
            query_id=response.query_id,
            response_text=response.response_text or "",
            retrieved_context_ids=context_ids,
            llm_model=response.llm_model,
            latency_ms=response.latency_ms,
            tags=tags,
            language_response=lang_resp,
            response_metadata=metadata,
        )
        db.add(db_response)
        logger.debug("Before commit")
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("❌ Update failed: %s", e)
            return None
        logger.debug("After commit")
        db.refresh(db_response)
        logger.info("✅ QueryResponse inserted: id=%s query_id=%s", db_response.id, db_response.query_id)
        return db_response
    except Exception as e:
        db.rollback()
        logger.error("❌ Response insert failed: %s", e, exc_info=True)
        raise


def get_response_by_id(db: Session, response_id: int) -> Optional[models.QueryResponse]:
    return db.query(models.QueryResponse).filter(models.QueryResponse.id == response_id).first()


def get_response_by_query_id(db: Session, query_id: int) -> Optional[models.QueryResponse]:
    """Return the response row linked to this query_id (for edit/regenerate flow)."""
    return (
        db.query(models.QueryResponse)
        .filter(models.QueryResponse.query_id == query_id)
        .order_by(desc(models.QueryResponse.id))
        .first()
    )


def update_response_content(
    db: Session,
    response_id: int,
    response_text: str,
    retrieved_context_ids: Optional[List[str]] = None,
    llm_model: Optional[str] = None,
    latency_ms: Optional[int] = None,
    tags: Optional[list] = None,
    language_response: Optional[dict] = None,
) -> Optional[models.QueryResponse]:
    """
    Update existing response row with new answer and optional metadata.
    Used when regenerating answer for same query_id; chat_messages links unchanged.
    """
    r = db.query(models.QueryResponse).filter(models.QueryResponse.id == response_id).first()
    if not r:
        return None
    r.response_text = response_text
    if retrieved_context_ids is not None:
        r.retrieved_context_ids = _safe_context_ids(retrieved_context_ids)
    if llm_model is not None:
        r.llm_model = llm_model
    if latency_ms is not None:
        r.latency_ms = latency_ms
    if tags is not None:
        r.tags = tags
    if language_response is not None:
        r.language_response = language_response
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(r)
    return r


# =============================================================================
# ChatSession (Phase 2)
# =============================================================================

def create_chat_session(db: Session, data: schemas.ChatSessionCreate, session_id: Optional[str] = None) -> models.ChatSession:
    session_id = session_id or data.session_id
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
    latest_metadata = get_latest_user_metadata(db, data.user_id)
    chat_session = models.ChatSession(
        user_id=data.user_id,
        session_id=session_id,
        session_metadata=latest_metadata,
    )
    db.add(chat_session)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(chat_session)
    return chat_session


def get_chat_session_by_session_id(db: Session, session_id: str) -> Optional[models.ChatSession]:
    return (
        db.query(models.ChatSession)
        .filter(models.ChatSession.session_id == session_id)
        .first()
    )


def get_chat_sessions_by_user(db: Session, user_id: str, limit: int = 100) -> List[models.ChatSession]:
    return (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.user_id == user_id,
            models.ChatSession.is_temporary.is_(False)
        )
        .order_by(desc(models.ChatSession.updated_at))
        .limit(limit)
        .all()
    )


def get_latest_user_metadata(db: Session, user_id: str) -> dict:
    """Finds the most recently updated session for this user that has a profile name."""
    latest_session = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.user_id == user_id,
            models.ChatSession.session_metadata != None
        )
        .order_by(desc(models.ChatSession.updated_at))
        .first()
    )
    if latest_session and isinstance(latest_session.session_metadata, dict):
        # We only really want to inherit the Profile and Financials, not the chat memory
        meta = latest_session.session_metadata
        return {
            "profile": meta.get("profile", {}),
            "financials": meta.get("financials", {}),
            "notices": meta.get("notices", {}),
            "compliance": meta.get("compliance", {}),
            "deductions": meta.get("deductions", {})
        }
    return {}


def update_chat_session(db: Session, session_id: str, data: schemas.ChatSessionUpdate) -> Optional[models.ChatSession]:
    chat = get_chat_session_by_session_id(db, session_id)
    if not chat:
        return None
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(chat)
    return chat


def update_chat_session_history(db: Session, session_id: str, history: dict) -> Optional[models.ChatSession]:
    """
    Set chat_sessions.history JSON to the given dict (e.g. {"title": "...", "first_question": "..."}).
    Used by Fintax-style sidebar; no new tables.
    """
    chat = get_chat_session_by_session_id(db, session_id)
    if not chat:
        return None
    chat.history = history if history is not None else {}
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(chat)
    return chat


def deep_merge_dict(dest: dict, src: dict) -> dict:
    """Recursively deeply merges src into dest. Missing keys are added, existing dicts are merged."""
    if not isinstance(dest, dict) or not isinstance(src, dict):
        return src if isinstance(src, dict) else (dest if isinstance(dest, dict) else {})
    for key, val in src.items():
        if isinstance(val, dict) and key in dest and isinstance(dest[key], dict):
            dest[key] = deep_merge_dict(dest[key], val)
        else:
            dest[key] = val
    return dest


def update_session_metadata(db: Session, session_id: str, updates: dict) -> Optional[models.ChatSession]:
    """Deep merges given updates into the chat session's rich metadata."""
    chat = get_chat_session_by_session_id(db, session_id)
    if not chat:
        return None
        
    current = chat.session_metadata
    if not isinstance(current, dict):
        current = {}
        
    import copy
    new_metadata = copy.deepcopy(current)
    new_metadata = deep_merge_dict(new_metadata, updates)
    
    chat.session_metadata = new_metadata
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ session_metadata Update failed: %s", e)
        return None
    db.refresh(chat)
    return chat


def delete_chat_session(db: Session, session_id: str) -> bool:
    chat = get_chat_session_by_session_id(db, session_id)
    if not chat:
        return False
    
    try:
        # 1. Delete associated ChatMessages
        db.query(models.ChatMessage).filter(
            models.ChatMessage.session_id == session_id
        ).delete(synchronize_session=False)
        
        # 2. Delete associated QueryResponses (🔥 FIXED HERE)
        db.query(models.QueryResponse).filter(
            models.QueryResponse.query_id.in_(
                db.query(models.UserQuery.id).filter(models.UserQuery.session_id == session_id)
            )
        ).delete(synchronize_session=False)
        
        # 3. Delete associated UserQueries
        db.query(models.UserQuery).filter(
            models.UserQuery.session_id == session_id
        ).delete(synchronize_session=False)
        
        # 4. Delete FileUploads
        db.query(models.FileUpload).filter(
            models.FileUpload.session_id == session_id
        ).delete(synchronize_session=False)
        
        # 5. Delete ChatSession
        db.delete(chat)
        db.commit()
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to delete session {session_id}: {e}", exc_info=True)
        return False


# =============================================================================
# ChatMessage (Phase 2)
# =============================================================================

def _normalize_react(value) -> str:
    """Ensure react is emoji string or 'no_react'; never store boolean 'true'/'false'."""
    if value is None:
        return "no_react"
    if isinstance(value, bool):
        return "no_react"
    s = (value if isinstance(value, str) else str(value)).strip()
    if not s or s.lower() in ("true", "false"):
        return "no_react"
    return s


def create_chat_message(db: Session, data: schemas.ChatMessageCreate) -> models.ChatMessage:
    """Create a new chat message. Safe transaction: rollback on failure so session stays valid."""
    msg = models.ChatMessage(
        session_id=data.session_id,
        query_id=data.query_id,
        response_id=data.response_id,
        react=_normalize_react(getattr(data, "react", "no_react")),
        tags=data.tags,
        feedback=data.feedback,
    )
    try:
        db.add(msg)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("❌ Update failed: %s", e)
            return None
        db.refresh(msg)
        return msg
    except Exception as e:
        db.rollback()
        logger.error("❌ ChatMessage insert failed: %s", e, exc_info=True)
        raise


def get_chat_message_by_id(db: Session, message_id: int) -> Optional[models.ChatMessage]:
    return db.query(models.ChatMessage).filter(models.ChatMessage.id == message_id).first()


def get_chat_messages_by_session(db: Session, session_id: str, favourites_only: bool = False, limit: int = 100) -> List[models.ChatMessage]:
    q = db.query(models.ChatMessage).filter(models.ChatMessage.session_id == session_id)
    if favourites_only:
        q = q.filter(models.ChatMessage.react != "no_react").filter(~models.ChatMessage.react.in_(["true", "false"]))
    return q.order_by(desc(models.ChatMessage.created_at)).limit(limit).all()


def get_chat_message_by_session_and_query(
    db: Session, session_id: str, query_id: int
) -> Optional[models.ChatMessage]:
    """Return the single chat_message row for this session + query (for edit flow ordering)."""
    return (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.session_id == session_id,
            models.ChatMessage.query_id == query_id,
        )
        .first()
    )


def set_message_metadata_merge(db: Session, message_id: int, merge: dict) -> Optional[models.ChatMessage]:
    """Merge merge dict into message.message_metadata (e.g. {"hidden": True}). Commit immediately."""
    msg = get_chat_message_by_id(db, message_id)
    if not msg:
        return None
    current = (msg.message_metadata or {}) if isinstance(msg.message_metadata, dict) else {}
    current.update(merge)
    msg.message_metadata = current
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(msg)
    return msg


def hide_messages_after_query(db: Session, session_id: str, query_id: int) -> int:
    """
    Find all chat_messages in session after the message for query_id (by created_at).
    Set metadata.hidden = true on each; do not delete. Returns count of messages updated.
    Commits once after all updates to avoid orphaned state.
    """
    from sqlalchemy import asc

    pivot_msg = get_chat_message_by_session_and_query(db, session_id, query_id)
    if not pivot_msg:
        return 0
    pivot_created = pivot_msg.created_at

    # All messages in this session with created_at > pivot (strictly after)
    future = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.session_id == session_id,
            models.ChatMessage.created_at > pivot_created,
        )
        .order_by(asc(models.ChatMessage.created_at))
        .all()
    )
    for msg in future:
        current = (msg.message_metadata or {}) if isinstance(msg.message_metadata, dict) else {}
        current["hidden"] = True
        msg.message_metadata = current
    if future:
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("❌ Update failed: %s", e)
            return None
        for m in future:
            db.refresh(m)
    return len(future)


def get_session_messages_joined(
    db: Session, session_id: str, limit: int = 500, exclude_hidden: bool = False
) -> List[dict]:
    """
    Return full conversation for a session: join chat_messages, user_queries, query_responses.
    Order by message created_at ASC. Each item: query_text, response_text, created_at, message_id, query_id, response_id, message_metadata, etc.
    When exclude_hidden=True, messages with metadata.hidden=true are omitted (for visible context / LLM).
    """
    from sqlalchemy import asc

    rows = (
        db.query(
            models.ChatMessage.id.label("message_id"),
            models.ChatMessage.created_at,
            models.ChatMessage.react,
            models.ChatMessage.feedback,
            models.ChatMessage.message_metadata.label("message_metadata"),
            models.UserQuery.id.label("query_id"),
            models.UserQuery.query_text,
            models.UserQuery.category,
            models.UserQuery.query_metadata,
            models.UserQuery.created_at.label("query_created_at"),
            models.QueryResponse.id.label("response_id"),
            models.QueryResponse.response_text,
            models.QueryResponse.created_at.label("response_created_at"),
        )
        .join(models.UserQuery, models.ChatMessage.query_id == models.UserQuery.id)
        .join(models.QueryResponse, models.ChatMessage.response_id == models.QueryResponse.id)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(asc(models.ChatMessage.created_at))
        .limit(limit * 2 if exclude_hidden else limit)
        .all()
    )
    out = []
    for r in rows:
        meta = r.message_metadata if isinstance(r.message_metadata, dict) else {}
        if exclude_hidden and meta.get("hidden") is True:
            continue
        out.append({
            "message_id": r.message_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "react": _normalize_react(r.react),
            "feedback": r.feedback,
            "query_id": r.query_id,
            "query_text": r.query_text,
            "category": r.category,
            "query_metadata": r.query_metadata if isinstance(r.query_metadata, dict) else {},
            "query_created_at": r.query_created_at.isoformat() if r.query_created_at else None,
            "response_id": r.response_id,
            "response_text": r.response_text,
            "response_created_at": r.response_created_at.isoformat() if r.response_created_at else None,
            "message_metadata": meta,
        })
        if len(out) >= limit:
            break
    return out


def get_favourites_by_user(db: Session, user_id: str, limit: int = 100) -> List[models.ChatMessage]:
    """Get all favourite messages for a user (react is emoji, not 'no_react' or legacy 'true'/'false')."""
    return (
        db.query(models.ChatMessage)
        .join(models.ChatSession, models.ChatMessage.session_id == models.ChatSession.session_id)
        .filter(models.ChatSession.user_id == user_id)
        .filter(models.ChatMessage.react != "no_react")
        .filter(~models.ChatMessage.react.in_(["true", "false"]))
        .order_by(desc(models.ChatMessage.created_at))
        .limit(limit)
        .all()
    )


def verify_message_ownership(db: Session, message_id: int, user_id: str) -> bool:
    """Verify that a message belongs to a specific user."""
    msg = get_chat_message_by_id(db, message_id)
    if not msg:
        return False
    # Get the session to check user_id
    session = get_chat_session_by_session_id(db, msg.session_id)
    if not session:
        return False
    # Compare user_ids (handle case where session might have "anonymous" but user_id matches)
    # If session user_id is "anonymous", allow if user_id also matches or if it's a new user
    if session.user_id == "anonymous" and user_id != "anonymous":
        # Update session with actual user_id for future requests
        try:
            session.user_id = user_id
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("❌ Update failed: %s", e)
                return None
            db.refresh(session)
            return True
        except Exception:
            db.rollback()
            return False
    return session.user_id == user_id


def update_chat_message(db: Session, message_id: int, data: schemas.ChatMessageUpdate) -> Optional[models.ChatMessage]:
    msg = get_chat_message_by_id(db, message_id)
    if not msg:
        return None
    if data.react is not None:
        msg.react = _normalize_react(data.react)
    if data.tags is not None:
        msg.tags = data.tags
    if data.feedback is not None:
        msg.feedback = data.feedback
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(msg)
    return msg


def delete_chat_message(db: Session, message_id: int) -> bool:
    msg = get_chat_message_by_id(db, message_id)
    if not msg:
        return False
    db.delete(msg)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    return True


# =============================================================================
# Subscription (Phase 2)
# =============================================================================

def create_subscription(db: Session, data: schemas.SubscriptionCreate) -> models.Subscription:
    sub = models.Subscription(
        user_id=data.user_id,
        plan_type=data.plan_type,
        features=data.features,
        usage_limits=data.usage_limits,
        expires_at=data.expires_at,
    )
    db.add(sub)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(sub)
    return sub


def get_subscription_by_user(db: Session, user_id: str) -> Optional[models.Subscription]:
    return db.query(models.Subscription).filter(models.Subscription.user_id == user_id).first()


def update_subscription(db: Session, user_id: str, data: schemas.SubscriptionUpdate) -> Optional[models.Subscription]:
    sub = get_subscription_by_user(db, user_id)
    if not sub:
        return None
    if data.plan_type is not None:
        sub.plan_type = data.plan_type
    if data.features is not None:
        sub.features = data.features
    if data.usage_limits is not None:
        sub.usage_limits = data.usage_limits
    if data.expires_at is not None:
        sub.expires_at = data.expires_at
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(sub)
    return sub


def delete_subscription(db: Session, user_id: str) -> bool:
    sub = get_subscription_by_user(db, user_id)
    if not sub:
        return False
    db.delete(sub)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    return True


# =============================================================================
# FileUpload (Phase 2)
# =============================================================================

def create_file_upload(db: Session, data: schemas.FileUploadCreate) -> models.FileUpload:
    fu = models.FileUpload(
        user_id=data.user_id,
        session_id=data.session_id,
        file_path=data.file_path,
        file_type=data.file_type,
        tags=data.tags,
    )
    db.add(fu)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(fu)
    return fu


def get_file_upload_by_id(db: Session, file_id: int) -> Optional[models.FileUpload]:
    return db.query(models.FileUpload).filter(models.FileUpload.id == file_id).first()


def get_file_uploads_by_user(db: Session, user_id: str, session_id: Optional[str] = None, folder: Optional[str] = None, limit: int = 100) -> List[models.FileUpload]:
    q = db.query(models.FileUpload).filter(models.FileUpload.user_id == user_id)
    if session_id is not None:
        q = q.filter(models.FileUpload.session_id == session_id)
    if folder is not None:
        q = q.filter(models.FileUpload.tags == folder)
    return q.order_by(desc(models.FileUpload.uploaded_at)).limit(limit).all()


def update_file_upload(db: Session, file_id: int, data: schemas.FileUploadUpdate) -> Optional[models.FileUpload]:
    fu = get_file_upload_by_id(db, file_id)
    if not fu:
        return None
    if data.tags is not None:
        fu.tags = data.tags
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(fu)
    return fu


def delete_file_upload(db: Session, file_id: int) -> bool:
    fu = get_file_upload_by_id(db, file_id)
    if not fu:
        return False
    db.delete(fu)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    return True


# =============================================================================
# Message reaction (single emoji in chat_messages.react)
# =============================================================================

def set_message_reaction(db: Session, message_id: int, user_id: str, emoji: str) -> Optional[models.ChatMessage]:
    """
    Set the single emoji reaction for a message. Only updates if message belongs to user's session.
    Empty emoji → store 'no_react'. Returns updated ChatMessage or None.
    """
    if not verify_message_ownership(db, message_id, user_id):
        return None
    msg = get_chat_message_by_id(db, message_id)
    if not msg:
        return None
    msg.react = _normalize_react(emoji)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("❌ Update failed: %s", e)
        return None
    db.refresh(msg)
    return msg


def get_message_reaction(db: Session, message_id: int) -> str:
    """Return the stored reaction emoji for a message (or 'no_react')."""
    msg = get_chat_message_by_id(db, message_id)
    if not msg:
        return "no_react"
    return _normalize_react(getattr(msg, "react", None))

