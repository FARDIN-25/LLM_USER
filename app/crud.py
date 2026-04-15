from sqlalchemy.orm import Session
from app import models, schemas
from datetime import datetime, timedelta
from sqlalchemy import desc
from typing import List


def create_query(db: Session, query: schemas.QueryCreate):
    """Create a new user query."""
    # Support both query_text and question fields
    query_text = query.get_question_text() if hasattr(query, 'get_question_text') else (query.query_text or query.question or "")
    
    db_query = models.UserQuery(
        query_text=query_text,
        user_id=query.user_id,
        session_id=query.session_id,
        language=query.language,
        query_metadata=query.query_metadata
    )
    db.add(db_query)
    db.commit()
    db.refresh(db_query)
    return db_query


def create_response(db: Session, response: schemas.ResponseCreate):
    """Create a new query response."""
    db_response = models.QueryResponse(
        query_id=response.query_id,
        response_text=response.response_text,
        retrieved_context_ids=response.retrieved_context_ids,
        llm_model=response.llm_model,
        latency_ms=response.latency_ms,
        response_metadata=response.response_metadata
    )
    db.add(db_response)
    db.commit()
    db.refresh(db_response)
    return db_response


def get_recent_queries(db: Session, hours: int = 24, limit: int = 100):
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(models.UserQuery)
        .filter(models.UserQuery.created_at >= cutoff_time)
        .order_by(desc(models.UserQuery.created_at))
        .limit(limit)
        .all()
    )


def search_queries(db: Session, search_term: str, limit: int = 50):
    return (
        db.query(models.UserQuery)
        .filter(models.UserQuery.query_text.ilike(f"%{search_term}%"))
        .limit(limit)
        .all()
    )

