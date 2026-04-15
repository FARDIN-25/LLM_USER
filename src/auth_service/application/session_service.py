import uuid
import logging
from typing import Tuple
from sqlalchemy.orm import Session
from datetime import datetime
from src.db_service.models import Session as SessionModel, ChatSession

logger = logging.getLogger("fintax")


def create_temporary_session(db: Session, user_id: str) -> ChatSession:
    """Create a new temporary chat session and commit."""

    session_id = f"tmp-{datetime.utcnow().strftime('%d%m%Y')}-{uuid.uuid4().hex[:8]}"

    chat_session = ChatSession(
        user_id=user_id,
        session_id=session_id,
        is_temporary=True,  # ⭐ IMPORTANT
    )

    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    return chat_session


def get_or_create_session(
    db: Session,
    user_id: str,
    session_id: str | None = None,
) -> Tuple[ChatSession, bool]:
    """
    Get existing ChatSession by session_id, or create new one. Returns (session, created).
    If session_id is None, generates a new one. Commits when creating.
    Updates user_id if session exists with "anonymous" and new user_id is provided.
    """
    if session_id:
        existing = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
        ).first()
        if existing:
            # Update user_id if it was "anonymous" and we have a real user_id
            if existing.user_id == "anonymous" and user_id != "anonymous":
                existing.user_id = user_id
                db.commit()
                db.refresh(existing)
            return existing, False
    sid = session_id or f"{datetime.utcnow().strftime('%d%m%Y')}-{uuid.uuid4().hex[:8]}"
    chat_session = ChatSession(
        user_id=user_id,
        session_id=sid,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session, True


def ensure_session_exists(db: Session, user_id: str) -> ChatSession:
    """
    If no active session for user → create one. Otherwise return existing.
    Used by chat flow so first message creates a history entry.
    """
    return get_or_create_active_session(db, user_id)


def get_session_for_user(db: Session, session_id: str, user_id: str) -> ChatSession | None:
    """
    Return ChatSession if it exists and belongs to the user. Otherwise None.
    Used for Fintax-style continuation: frontend sends session_id; backend validates ownership.
    """
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user_id,
    ).first()
    return session


def get_or_create_active_session(db: Session, user_id: str) -> ChatSession:
    """
    Always create a NEW session.
    Previous sessions remain in history.
    Used for "New Chat" or login landing.
    """

    session_id = f"{datetime.utcnow().strftime('%d%m%Y')}-{uuid.uuid4().hex[:8]}"

    chat_session = ChatSession(
        user_id=user_id,
        session_id=session_id,
    )

    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    return chat_session


def close_session(db: Session, session_id: str) -> bool:
    """
    Close (hard delete) a session.
    
    Args:
        db: Database session
        session_id: Session identifier to close
        
    Returns:
        bool: True if session was found and deleted, False otherwise
    """
    session = (
        db.query(ChatSession)
        .filter(ChatSession.session_id == session_id)
        .first()
    )
    
    if not session:
        logger.warning(f"Session {session_id} not found")
        return False
    
    db.delete(session)
    db.commit()
    logger.info(f"Session {session_id} closed successfully")
    return True


def close_current_and_create_new_session(db: Session, user_id: str) -> ChatSession:
    """
    Close the current active session for the user (if any), then create and return a new one.
    """
    active = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .first()
    )
    if active:
        close_session(db, active.session_id)
    return get_or_create_active_session(db, user_id)


def create_new_session(db: Session, user_id: str) -> ChatSession:
    """
    Create a new chat session without closing any previous one.
    Previous chats stay in history (sidebar). Used by "New Chat" when history must not be removed.
    """
    session_id = f"{datetime.utcnow().strftime('%d%m%Y')}-{uuid.uuid4().hex[:8]}"
    chat_session = ChatSession(
        user_id=user_id,
        session_id=session_id,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session


def track_session(db: Session, session_id: str) -> SessionModel:
    """Track or create a session and update its activity. Increments query_count for each call."""
    if not session_id:
        return None
    
    try:
        # Query for existing session
        session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        
        if not session:
            # Create new session with query_count = 1 (first query)
            session = SessionModel(
                session_id=session_id,
                created_at=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
                query_count=1
            )
            db.add(session)
            db.flush()  # Flush to get the ID
        else:
            # Update existing session - ALWAYS increment query count
            session.last_activity_at = datetime.utcnow()
            # Get current count and increment by 1
            current_count = int(session.query_count) if session.query_count is not None else 0
            session.query_count = current_count + 1
        
        # Commit the changes
        db.commit()
        # Refresh to get the latest data
        db.refresh(session)
        
        return session
    except Exception as e:
        db.rollback()
        import logging
        logger = logging.getLogger("fintax")
        logger.error(f"Error tracking session {session_id}: {e}", exc_info=True)
        # Don't raise, just log the error to prevent breaking the request
        return None

