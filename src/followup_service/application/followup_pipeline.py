import logging
from sqlalchemy.orm import Session

from src.shared.config import settings
from ..domain.followup_detector import FollowupDetector
from ..domain.followup_rewriter import FollowupRewriter
from ..infrastructure.history_repository import HistoryRepository

logger = logging.getLogger("fintax")


class FollowupPipeline:
    """
    Orchestrates the follow-up rewriting process by coordinating the detector,
    history repository, and LLM rewriter.
    """

    @classmethod
    async def process(cls, db: Session, session_id: str, question: str) -> tuple[str, bool]:
        """
        Executes the follow-up rewriting pipeline asynchronously.

        Args:
            db: SQLAlchemy Session
            session_id: The session ID indicating the conversation thread context
            question: The user's input question

        Returns:
            A tuple of (rewritten_question: str, is_followup: bool)
        """
        if not question or not session_id:
            return question, False

        # --- BYPASS FOR GREETINGS AND PERSONA ---
        # Greetings and persona questions ("Who is Bhaaskar?") never need context.
        q_low = question.lower().strip()
        greetings = ["hi", "hello", "hey", "hola", "greetings", "morning", "evening", "vanakkam", "bhaaskar"]
        if any(greet in q_low for greet in greetings):
            # If it's a short greeting or a persona question, don't rewrite it.
            if len(q_low.split()) <= 4 or "who is" in q_low or "what is" in q_low:
                return question, False

        # 1. Fetch the last query to improve detection precision
        prev_query = HistoryRepository.get_last_query(db, session_id)

        # 2. Detect if it's a follow-up (using prev_query for entity-overlap)
        is_followup = FollowupDetector.is_followup(question, previous_query=prev_query)
        if not is_followup:
            return question, False

        # 3. Extract conversation history
        # (Only fetch if it is indeed a follow-up to save overhead)
        try:
            history = HistoryRepository.get_history_text(db, session_id, limit=settings.REWRITE_HISTORY_TURNS)
            if not history:
                # Follow-up detected but no history available — preserve the detection result
                return question, True
        except Exception as e:
            logger.error(f"Failed to fetch interaction history: {e}")
            return question, True

        # 4. Rewrite using history context
        rewritten = await FollowupRewriter.rewrite(history, question)

        # If LLM returned the same question unchanged, still mark it as a follow-up
        # because detection already confirmed it — just skip the rewrite
        if not rewritten or rewritten.strip().lower() == question.strip().lower():
            return question, True

        return rewritten, True