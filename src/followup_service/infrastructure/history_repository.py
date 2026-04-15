from typing import Optional
from sqlalchemy.orm import Session
from src.db_service import crud

class HistoryRepository:
    """
    Responsible for retrieving the conversation history required for rewriting 
    follow-up questions.
    """

    @classmethod
    def get_history_text(cls, db: Session, session_id: str, limit: int = 10) -> str:
        """
        Retrieves the last N messages for the session and formats them as a 
        conversation log for the LLM.
        
        Args:
            db: SQLAlchemy Session
            session_id: The session to fetch from
            limit: Maximum number of previous interactions to fetch
            
        Returns:
            A formatted string of "User: ... \n Assistant: ..."
        """
        if not session_id:
            return ""

        # Fetch visible messages (exclude hidden) using existing project logic
        # This returns them ordered by time ASC (oldest first up to the current moment)
        messages = crud.get_session_messages_joined(db, session_id, limit=limit, exclude_hidden=True)
        
        if not messages:
            return ""
            
        # Format as conversation history text
        history_parts = []
        for msg in messages:
            user_q = msg.get("query_text", "").strip()
            assist_a = msg.get("response_text", "").strip()
            
            if user_q:
                history_parts.append(f"User: {user_q}")
            if assist_a:
                history_parts.append(f"Assistant: {assist_a}")
                
        return "\n".join(history_parts)

    @classmethod
    def get_history_list(cls, db: Session, session_id: str, limit: int = 10) -> list:
        """
        Returns history as a list of dicts: [{'role': 'user', 'content': '...'}, ...]
        """
        if not session_id:
            return []
            
        messages = crud.get_session_messages_joined(db, session_id, limit=limit, exclude_hidden=True)
        history = []
        for msg in messages:
            if msg.get("query_text"):
                history.append({"role": "user", "content": msg["query_text"]})
            if msg.get("response_text"):
                history.append({"role": "assistant", "content": msg["response_text"]})
        return history

    @classmethod
    def get_last_query(cls, db: Session, session_id: str) -> Optional[str]:
        """Fetches only the most recent user query from the session."""
        if not session_id:
            return None
        
        messages = crud.get_session_messages_joined(db, session_id, limit=1)
        if not messages:
            return None
            
        return messages[0].get("query_text")
