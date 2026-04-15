import logging
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from src.db_service import models
from src.category_service.application.category_service import normalize_category, ChatCategory

logger = logging.getLogger("fintax")


def calculate_session_badge(db: Session, session_id: str) -> str:
    """
    Calculate the dominant category (badge) for a chat session.

    Rules:
    1. Count user_queries.category values within the session.
    2. The category with the highest count becomes the badge.
    3. If multiple categories share the highest count (tie),
       use the category of the first question in the session
       (ordered by created_at ASC).
    4. If the first question's category is NULL/unknown, return GENERAL.

    This function is read-only and does not modify the database.
    """
    if not session_id:
        return ChatCategory.GENERAL.value

    # 1. Fetch all user_queries for this session, oldest first
    queries = (
        db.query(models.UserQuery)
        .filter(models.UserQuery.session_id == session_id)
        .order_by(models.UserQuery.created_at.asc())
        .all()
    )

    if not queries:
        return ChatCategory.GENERAL.value

    # 2. Count frequency using the current detection rules on query_text.
    # This keeps the sidebar/session badge correct even if older rows were saved
    # with a less-accurate rule set in the past.
    try:
        from src.category_service.application.category_service import detect_category

        normalized_categories = [
            normalize_category(detect_category(q.query_text or ""))
            for q in queries
        ]
    except Exception as e:
        # FIX: Log the actual error so it's not silently swallowed
        logger.warning(f"detect_category failed, falling back to stored categories: {e}")
        normalized_categories = [normalize_category(q.category) for q in queries]

    counts = Counter(normalized_categories)

    if not counts:
        return ChatCategory.GENERAL.value

    # 3. Highest count
    max_count = max(counts.values())
    top_categories = [cat for cat, cnt in counts.items() if cnt == max_count]

    # 4. Unique winner
    if len(top_categories) == 1:
        return top_categories[0]

    # 5. Tie: use first question's category when possible
    first_category = normalized_categories[0]
    if first_category in top_categories:
        return first_category

    # Fallback when first question has invalid/unknown category
    return ChatCategory.GENERAL.value


def get_session_category_counts_sql() -> str:
    """
    Helper to expose the raw SQL pattern for counting categories.

    Not executed directly; provided for documentation/ops tooling:

    SELECT
        COALESCE(NULLIF(UPPER(TRIM(category)), ''), 'GENERAL') AS norm_category,
        COUNT(*) AS cnt
    FROM user_queries
    WHERE session_id = :session_id
    GROUP BY norm_category;
    """
    return (
        "SELECT COALESCE(NULLIF(UPPER(TRIM(category)), ''), 'GENERAL') AS norm_category, "
        "COUNT(*) AS cnt "
        "FROM user_queries "
        "WHERE session_id = :session_id "
        "GROUP BY norm_category"
    )