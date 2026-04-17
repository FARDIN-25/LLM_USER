from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger("fintax")

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])

# Expected embedding dimension (matches all-MiniLM-L6-v2 model)
EXPECTED_EMBEDDING_DIM = 384

# Initialize embedding model (shared across requests)
try:
    from sentence_transformers import SentenceTransformer
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    EMBEDDING_MODEL_AVAILABLE = True
    logger.info(f"✅ Embedding model loaded: all-MiniLM-L6-v2 (dimension: {EXPECTED_EMBEDDING_DIM})")
except Exception as e:
    EMBEDDING_MODEL_AVAILABLE = False
    embedding_model = None
    logger.warning(f"⚠️ Embedding model not available: {e}")

# ---------------------------
# DB Dependency
# ---------------------------
def get_db():
    from src.db_service.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------
# Request / Response Models
# ---------------------------
class RetrievalRequest(BaseModel):
    query: str
    query_embedding: Optional[List[float]] = None  # Made optional
    k: int = 5
    use_sparse: bool = True

class RetrievalResponse(BaseModel):
    results: List[Dict]


# --------------------------------------------------
# 🔹 Import Core Logic
# --------------------------------------------------
from .search_logic import (
    dense_search_pgvector,
    hybrid_retrieve,
    sparse_search_postgres,
)


# --------------------------------------------------
# 🚀 FASTAPI ENDPOINT
# --------------------------------------------------
@router.post("/search", response_model=RetrievalResponse)
def search_endpoint(payload: RetrievalRequest, db: Session = Depends(get_db)):
    try:
        # Route the query (lookup vs semantic vs ambiguous)
        try:
            from src.retrieval.router import classify_query
            route = classify_query(payload.query).get("route", "ambiguous")
        except Exception as e:
            logger.warning(f"Query router failed, defaulting to ambiguous: {e}")
            route = "ambiguous"

        # Auto-generate embedding if not provided OR if dimension is wrong
        query_embedding = payload.query_embedding
        needs_regeneration = False
        
        if query_embedding is None:
            needs_regeneration = True
        elif len(query_embedding) != EXPECTED_EMBEDDING_DIM:
            # Wrong dimension - auto-generate instead
            needs_regeneration = True
            logger.warning(f"⚠️ Invalid embedding dimension: {len(query_embedding)}. Expected {EXPECTED_EMBEDDING_DIM}. Auto-generating from query text.")
        
        if needs_regeneration:
            if not EMBEDDING_MODEL_AVAILABLE:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"query_embedding is required when embedding model is not available. "
                        f"Please provide a {EXPECTED_EMBEDDING_DIM}-dimensional vector or ensure "
                        "sentence-transformers is installed."
                    )
                )
            
            logger.info(f"🔄 Auto-generating embedding for query: {payload.query}...")
            query_embedding = embedding_model.encode(payload.query).tolist()
            logger.info(f"✅ Generated {len(query_embedding)}-dimensional embedding")
        
        # Routed retrieval
        if route == "lookup":
            results = sparse_search_postgres(db, payload.query, k=payload.k * 2)
        elif route == "semantic":
            if not query_embedding:
                results = sparse_search_postgres(db, payload.query, k=payload.k * 2)
            else:
                results = hybrid_retrieve(
                    db=db,
                    query=payload.query,
                    query_embedding=query_embedding,
                    k=payload.k,
                )
        else:
            merged: List[Dict] = []
            if query_embedding:
                merged.extend(
                    hybrid_retrieve(
                        db=db,
                        query=payload.query,
                        query_embedding=query_embedding,
                        k=payload.k,
                    )
                )
            merged.extend(sparse_search_postgres(db, payload.query, k=payload.k * 2))

            # Dedup by doc.id, keep max score
            by_id: Dict[str, Dict] = {}
            for r in merged:
                did = str(r.get("doc", {}).get("id") or "")
                if not did:
                    continue
                prev = by_id.get(did)
                if prev is None or float(r.get("score") or 0) > float(prev.get("score") or 0):
                    by_id[did] = r
            results = sorted(by_id.values(), key=lambda x: float(x.get("score") or 0), reverse=True)[: payload.k]

        # PageIndex is the 3rd retrieval source. Route controls whether it's included.
        if results and results[0].get("doc", {}).get("content") == "NO_CONTEXT":
            return {"results": results}

        try:
            from src.page_index_service.database import page_index_session
            from src.page_index_service.retriever import page_index_search
            from src.shared.config import settings

            pi: List[Dict] = []
            if settings.PAGE_INDEX_DATABASE_URL:
                with page_index_session() as pdb:
                    pi = page_index_search(pdb, payload.query, k=payload.k * 2)

            if pi:
                # Map PageIndex to vector_service SearchResult shape
                pi_results: List[Dict] = []
                for item in pi:
                    pi_results.append(
                        {
                            "doc": {
                                "id": item.get("id"),
                                "content": item.get("text", ""),
                                "text": item.get("text", ""),
                                "metadata": item.get("metadata", {}),
                            },
                            "score": float(item.get("score") or 0),
                            "type": "page_index",
                        }
                    )

                if route == "lookup":
                    merged = list(results) + pi_results
                elif route == "semantic":
                    merged = list(results) + pi_results
                else:
                    merged = list(results) + pi_results

                # Dedup by doc.id, keep max score
                by_id: Dict[str, Dict] = {}
                for r in merged:
                    did = str(r.get("doc", {}).get("id") or "")
                    if not did:
                        continue
                    prev = by_id.get(did)
                    if prev is None or float(r.get("score") or 0) > float(prev.get("score") or 0):
                        by_id[did] = r
                results = sorted(by_id.values(), key=lambda x: float(x.get("score") or 0), reverse=True)[: payload.k]
        except Exception as e:
            logger.warning(f"PageIndex retrieval skipped/failed: {e}")
        
        return {"results": results}

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Check for dimension mismatch error
        if "different vector dimensions" in error_msg or "dimension" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Vector dimension mismatch: {error_msg}. "
                    f"Please provide a {EXPECTED_EMBEDDING_DIM}-dimensional embedding vector "
                    f"generated using SentenceTransformer('all-MiniLM-L6-v2'), or omit query_embedding "
                    "to auto-generate it from the query text."
                )
            )
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
