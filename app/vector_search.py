# app/vector_search.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import DocumentChunk
import logging

logger = logging.getLogger("tax_assistant")

def semantic_search(
    db: Session,
    query_embedding: list,
    top_k: int = 5
):
    """
    Semantic search using pgvector cosine similarity.
    Converts embedding list to PostgreSQL vector format.
    """
    # Convert Python list to PostgreSQL vector string format: '[0.1,0.2,0.3]'
    embedding_str = '[' + ','.join(str(float(x)) for x in query_embedding) + ']'
    
    # Use parameterized query with proper vector casting
    sql = text("""
        SELECT id, chunk_text, metadata as chunk_metadata
        FROM document_chunks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> (:query_embedding)::vector
        LIMIT :top_k
    """)

    try:
        rows = db.execute(
            sql,
            {
                "query_embedding": embedding_str,
                "top_k": top_k
            }
        ).fetchall()
    except Exception as e:
        logger.error(f"❌ Vector search error: {e}", exc_info=True)
        # Rollback and re-raise
        db.rollback()
        raise

    return [
        {
            "id": r.id,
            "text": r.chunk_text,
            "content": r.chunk_text,  # Add content alias
            "metadata": r.chunk_metadata if r.chunk_metadata else {}
        }
        for r in rows
    ]

