"""Main routes - API info, health, diagnostics and small utilities.

All API routes in this module are mounted under the shared prefix
`/api/user` by the application. Keep these endpoints JSON-only and
lightweight so they are suitable for liveness/readiness probes.
"""

from fastapi import APIRouter, Request
import logging
import platform
from datetime import datetime, timedelta
from sqlalchemy import desc


from sqlalchemy import text

from app.database import engine

logger = logging.getLogger("fintax")

router = APIRouter(tags=["Main"])


@router.get("/info")
def api_info():
    """Return basic service information."""
    return {
        "service": "LLM User Service",
        "status": "running",
        "description": "User Query & RAG Service"
    }


@router.get("/health")
def health(request: Request):
    """Lightweight health endpoint suitable for Kubernetes probes.

    Returns basic connectivity flags. Keep the response small and fast.
    """
    state = request.app.state

    database_connected = False
    vectorstore_initialized = False

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            database_connected = True

            result = conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'document_chunks'
                    )
                """)
            )
            vectorstore_initialized = bool(result.scalar())
    except Exception as e:
        logger.warning(f"DB health check failed: {e}")

    status = "healthy" if database_connected else "degraded"

    return {
        "status": status,
        "database_connected": database_connected,
        "vectorstore_initialized": vectorstore_initialized,
        "langchain_available": vectorstore_initialized,
        "query_expansion_available": getattr(state, "QUERY_EXPANSION_AVAILABLE", False),
        "reranking_available": getattr(state, "RERANKER_AVAILABLE", False),
        "llm_configured": bool(getattr(state, "OPENROUTER_API_KEY", "")),
    }


@router.get("/metrics")
def metrics():
    """Return small set of operational metrics.

    Keep this endpoint inexpensive; it can be extended later to
    emit Prometheus-compatible metrics (not implemented here).
    """
    db_connected = False
    query_count_30d = 0
    chunk_count = 0
    kb_files_count = 0
    llm_response_count = 0
    kb_chunks_used_30d = 0
    llm_response_chars_30d = 0
    kb_contribution_pct = 0.0
    llm_contribution_pct = 100.0

    try:
        with engine.connect() as conn:
            db_connected = True
            q = conn.execute(text("SELECT COUNT(1) FROM user_queries WHERE created_at >= NOW() - INTERVAL '30 days'"))
            query_count_30d = int(q.scalar() or 0)

            c = conn.execute(text("SELECT COUNT(1) FROM document_chunks"))
            chunk_count = int(c.scalar() or 0)

            # Count unique source files ingested into the KB. Use file_path when available, otherwise fall back to source_name.
            f = conn.execute(text("SELECT COUNT(DISTINCT COALESCE(NULLIF(file_path, ''), source_name)) FROM document_chunks"))
            kb_files_count = int(f.scalar() or 0)

            # Count LLM responses in the same 30 day window to align with queries_last_30d
            r = conn.execute(text("SELECT COUNT(1) FROM query_responses WHERE created_at >= NOW() - INTERVAL '30 days'"))
            llm_response_count = int(r.scalar() or 0)

            # Sum of KB chunks that were actually used in responses (cardinality of retrieved_context_ids)
            kc = conn.execute(text("SELECT COALESCE(SUM(COALESCE(cardinality(retrieved_context_ids),0)),0) FROM query_responses WHERE created_at >= NOW() - INTERVAL '30 days'"))
            kb_chunks_used_30d = int(kc.scalar() or 0)

            # Sum of response sizes (characters) as a lightweight proxy for LLM work
            lc = conn.execute(text("SELECT COALESCE(SUM(COALESCE(LENGTH(response_text),0)),0) FROM query_responses WHERE created_at >= NOW() - INTERVAL '30 days'"))
            llm_response_chars_30d = int(lc.scalar() or 0)

            # Contribution heuristic:
            # - If no KB chunks were used during period, LLM = 100%
            # - Otherwise, compute weighted contributions where KB weight = kb_chunks_used_30d
            #   and LLM weight = llm_response_chars_30d / CHAR_PER_TOKEN_ESTIMATE
            # - This is an explainable, backend-side heuristic (not a relevance score)
            CHAR_PER_TOKEN = 4.0
            if kb_chunks_used_30d <= 0:
                kb_contribution_pct = 0.0
                llm_contribution_pct = 100.0
            else:
                llm_equiv = (llm_response_chars_30d / CHAR_PER_TOKEN) if llm_response_chars_30d > 0 else 0.0
                kb_weight = float(kb_chunks_used_30d)
                llm_weight = float(llm_equiv)
                total_weight = kb_weight + llm_weight if (kb_weight + llm_weight) > 0 else 1.0
                kb_contribution_pct = max(0.0, min(100.0, (kb_weight / total_weight) * 100.0))
                llm_contribution_pct = max(0.0, min(100.0, 100.0 - kb_contribution_pct))

    except Exception as e:
        logger.warning(f"Metrics db query failed: {e}")

    # Round percentages to one decimal place for display
    kb_contribution_pct = round(kb_contribution_pct, 1)
    llm_contribution_pct = round(llm_contribution_pct, 1)

    # Return both the new canonical fields and a few backward-compatible aliases used by the UI
    return {
        "database_connected": db_connected,
        "queries_last_30d": query_count_30d,
        "document_chunks": chunk_count,
        "kb_files_count": kb_files_count,
        "kb_files": kb_files_count,  # backward compatibility
        "llm_response_count": llm_response_count,
        "total_responses": llm_response_count,  # backward compatibility
        "kb_chunks_used": kb_chunks_used_30d,
        "kb_contribution_percentage": kb_contribution_pct,
        "llm_contribution_percentage": llm_contribution_pct,
    }


@router.get("/storage-status")
def storage_status():
    """Return a simple storage status object for the UI."""
    # Provide a lightweight storage summary. We don't track actual bytes here,
    # but we can report the number of unique files known to the KB (document_chunks).
    file_count = 0
    try:
        with engine.connect() as conn:
            f = conn.execute(text("SELECT COUNT(DISTINCT COALESCE(NULLIF(file_path, ''), source_name)) FROM document_chunks"))
            file_count = int(f.scalar() or 0)
    except Exception:
        file_count = 0

    return {
        "usage_percent": 0,
        "total_size_gb": 0,
        "max_storage_size_gb": 130,
        "available_space_gb": 130,
        "file_count": file_count,
        "warning": False,
        "critical": False,
    }


@router.get("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools_manifest():
    """Return a minimal Chrome DevTools app-specific manifest to satisfy devtools requests."""
    return {
        "name": "LLM User Service",
        "description": "DevTools app manifest",
        "manifest_version": 1,
    }


@router.get("/upload-limits")
def upload_limits():
    """Return upload limits used by the UI."""
    return {
        "max_files_per_request": 100,
        "max_content_length_mb": 1024,
        "allowed_types": [".pdf", ".txt", ".docx", ".csv", ".xlsx"],
    }


@router.get("/diagnostics")
def diagnostics(request: Request):
    """Return diagnostic information about the running service."""
    state = request.app.state

    diag = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "system": {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "python_version": platform.python_version(),
            "machine": platform.machine(),
        },
        "components": {
            "database": {"connected": state.DB_AVAILABLE, "type": "PostgreSQL (pgvector)"},
            "reranker": {"available": state.RERANKER_AVAILABLE},
            "query_expansion": {"available": state.QUERY_EXPANSION_AVAILABLE},
            "llm": {"provider": "OpenRouter", "model": state.OPENROUTER_MODEL},
        },
        "cache": state.response_cache.summary() if hasattr(state, "response_cache") else {},
    }

    return diag


@router.get("/history")
def history_api(limit: int = 100):
    """Return recent query history (last 30 days) as JSON.

    This endpoint is intentionally lightweight and returns recent queries
    and the first response for each query (if available).
    """
    # We import lazily to avoid circular imports at router import time
    from app.database import get_db
    from app import models
    from sqlalchemy.orm import Session as _Session
    from app.database import SessionLocal

    # Try to obtain a DB session
    try:
        db: _Session = SessionLocal()
    except Exception:
        db = None

    try:
        if not db:
            return {"queries": []}

        cutoff = datetime.utcnow() - timedelta(days=30)
        queries = (
            db.query(models.UserQuery)
            .filter(models.UserQuery.created_at >= cutoff)
            .order_by(desc(models.UserQuery.created_at))
            .limit(limit)
            .all()
        )

        result = []
        CHAR_PER_TOKEN = 4.0
        for q in queries:
            response = (
                db.query(models.QueryResponse)
                .filter(models.QueryResponse.query_id == q.id)
                .first()
            )

            # Default contribution fields
            kb_contrib = {"percentage": 0.0, "chunks_count": 0, "context_chars": 0, "sources": []}
            llm_contrib = {"percentage": 100.0, "response_chars": 0, "total_tokens": 0, "model": None}

            if response:
                retrieved = response.retrieved_context_ids or []
                chunks_count = len(retrieved)

                # Gather chunk text and source information for the retrieved context ids
                kb_context_chars = 0
                sources = []
                if chunks_count > 0:
                    try:
                        chunks = db.query(models.DocumentChunk).filter(models.DocumentChunk.id.in_(retrieved)).all()
                        for ch in chunks:
                            text_len = len(ch.chunk_text or "")
                            kb_context_chars += text_len
                            src = ch.file_path or ch.source_name or None
                            if src:
                                sources.append(src)
                        # Deduplicate sources while preserving order
                        seen = set()
                        dedup_sources = []
                        for s in sources:
                            if s not in seen:
                                seen.add(s)
                                dedup_sources.append(s)
                        sources = dedup_sources
                    except Exception:
                        sources = []
                        kb_context_chars = 0

                response_chars = len(response.response_text or "")
                total_tokens = int(response_chars / CHAR_PER_TOKEN) if response_chars > 0 else 0

                # Per-query contribution heuristic (same approach as /metrics):
                if chunks_count <= 0:
                    kb_pct = 0.0
                    llm_pct = 100.0
                else:
                    llm_equiv = (response_chars / CHAR_PER_TOKEN) if response_chars > 0 else 0.0
                    kb_weight = float(chunks_count)
                    llm_weight = float(llm_equiv)
                    total = kb_weight + llm_weight if (kb_weight + llm_weight) > 0 else 1.0
                    kb_pct = max(0.0, min(100.0, (kb_weight / total) * 100.0))
                    llm_pct = max(0.0, min(100.0, 100.0 - kb_pct))

                kb_contrib = {
                    "percentage": round(kb_pct, 1),
                    "chunks_count": chunks_count,
                    "context_chars": kb_context_chars,
                    "sources": sources,
                }

                llm_contrib = {
                    "percentage": round(llm_pct, 1),
                    "response_chars": response_chars,
                    "total_tokens": total_tokens,
                    "model": response.llm_model,
                }

            result.append({
                "id": q.id,
                "question": q.query_text,
                "answer": response.response_text if response else None,
                "timestamp": q.created_at.isoformat(),
                "kb_contribution": kb_contrib,
                "llm_contribution": llm_contrib,
            })

        return {"queries": result}
    except Exception as e:
        logger.error("History API failed", exc_info=True)
        return {"queries": [], "error": str(e)}
    finally:
        try:
            if db:
                db.close()
        except Exception:
            pass

