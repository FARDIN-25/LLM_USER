"""
LLM User Service - Main Application.
Handles user queries, RAG pipeline, and responses.
"""

from contextlib import asynccontextmanager
import os
import logging 
import sys

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.shared.config import settings
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db_service.database import get_db, engine, SessionLocal
from src.db_service import models
from src.db_service import crud
from src.admin_service.api import routes as admin_routes
from src.chat_service.api import routes as chat_routes
from src.ingestion_service.api import routes as ingestion_routes
from src.auth_service.api import routes as auth_routes
from src.user_service.api import routes as user_routes
from src.category_service.api import routes as category_routes
from src.history_search_service.api import routes as history_search_routes
from src.vector_service.infrastructure.search_service import get_search_service
from src.user_onboarding_service.api.routes import router as onboarding_router
from src.chat_service.api.debug_routes import router as debug_router

from src.shared.logging import setup_logging, logger
from src.shared.exceptions import (
    BaseAppException, 
    app_exception_handler, 
    global_exception_handler
)

# Setup logging
setup_logging()

# -------------------------------------------------
# APP STATE INITIALIZATION
# -------------------------------------------------
def init_app_state(app: FastAPI):
    """Initialize application state."""
    # Database availability
    app.state.DB_AVAILABLE = True
    
    # Query expansion availability (comprehensive check)
    app.state.QUERY_EXPANSION_AVAILABLE = False
    app.state.QUERY_EXPANSION_STRATEGIES = []
    try:
        from src.rag_service.application.query_expansion_service import get_expansion_service
        expansion_service = get_expansion_service()
        app.state.QUERY_EXPANSION_AVAILABLE = expansion_service.is_available()
        app.state.QUERY_EXPANSION_STRATEGIES = expansion_service.get_available_strategies()
        if app.state.QUERY_EXPANSION_AVAILABLE:
            logger.info(f"✅ Query expansion service loaded successfully. Available strategies: {app.state.QUERY_EXPANSION_STRATEGIES}")
        else:
            logger.warning("⚠️ No query expansion strategies available")
    except ImportError as e:
        logger.warning(f"⚠️ Query expansion service not available: {e}")
        app.state.QUERY_EXPANSION_AVAILABLE = False
        app.state.QUERY_EXPANSION_STRATEGIES = []
    except Exception as e:
        logger.error(f"❌ Query expansion initialization failed: {e}", exc_info=True)
        app.state.QUERY_EXPANSION_AVAILABLE = False
        app.state.QUERY_EXPANSION_STRATEGIES = []
    
    # Reranker availability (comprehensive check)
    app.state.RERANKER_AVAILABLE = False
    app.state.RERANKER_TYPES = []
    try:
        from src.rag_service.infrastructure.reranking_service import get_reranking_service
        reranking_service = get_reranking_service()
        app.state.RERANKER_AVAILABLE = reranking_service.is_available()
        app.state.RERANKER_TYPES = reranking_service.get_available_types()
        if app.state.RERANKER_AVAILABLE:
            logger.info(f"✅ Reranking service loaded successfully. Available types: {app.state.RERANKER_TYPES}")
        else:
            logger.warning("⚠️ No rerankers available")
    except ImportError as e:
        logger.warning(f"⚠️ Reranking service module not available: {e}")
        app.state.RERANKER_AVAILABLE = False
        app.state.RERANKER_TYPES = []
    except Exception as e:
        logger.error(f"❌ Reranking service initialization failed: {e}", exc_info=True)
        app.state.RERANKER_AVAILABLE = False
        app.state.RERANKER_TYPES = []
    
    # Hybrid retrieval availability
    app.state.HYBRID_RETRIEVAL_AVAILABLE = False
    try:
        from src.vector_service.infrastructure.hybrid_retrieval import hybrid_retrieve, dense_search_pgvector
        # Test that functions are callable
        if callable(hybrid_retrieve) and callable(dense_search_pgvector):
            app.state.HYBRID_RETRIEVAL_AVAILABLE = True
            logger.info("✅ Hybrid retrieval module loaded successfully")
        else:
            app.state.HYBRID_RETRIEVAL_AVAILABLE = False
    except ImportError as e:
        logger.warning(f"⚠️ Hybrid retrieval module not available: {e}")
        app.state.HYBRID_RETRIEVAL_AVAILABLE = False
    except Exception as e:
        logger.error(f"❌ Hybrid retrieval initialization failed: {e}", exc_info=True)
        app.state.HYBRID_RETRIEVAL_AVAILABLE = False
    
    # LLM configuration via Settings
    app.state.MISTRAL_API_KEY = settings.MISTRAL_API_KEY
    app.state.MISTRAL_MODEL = settings.MISTRAL_MODEL
    
    # LLM availability config (no strict startup test; rely on runtime + background monitor)
    app.state.LLM_AVAILABLE = False
    app.state.LLM_STATUS = "Unknown"
    app.state.LLM_MODEL_NAME = settings.MISTRAL_MODEL

    if settings.MISTRAL_API_KEY:
        # Treat LLM as configured and tentatively available; actual calls handle retries/errors.
        app.state.LLM_AVAILABLE = True
        app.state.LLM_STATUS = "Configured (startup test skipped)"
        logger.info(
            f"🔧 LLM configured with model '{settings.MISTRAL_MODEL}'. "
            f"Startup connectivity test is skipped; availability will be verified at runtime."
        )
    else:
        app.state.LLM_STATUS = "API Key Missing"
        logger.warning("⚠️ MISTRAL_API_KEY not set. LLM features will be disabled.")
    
    # Response cache (simple dict-based cache)
    class SimpleCache:
        def summary(self):
            return {"size": 0, "hits": 0, "misses": 0}
    app.state.response_cache = SimpleCache()


# -------------------------------------------------
# APP LIFESPAN
# -------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Guard against duplicate execution
    if hasattr(app.state, '_startup_complete'):
        logger.warning("⚠️ Startup already completed, skipping duplicate initialization")
        yield
        return
    
    # Startup
    logger.info("🚀 LLM User Service starting with PostgreSQL + pgvector")
    logger.info("=" * 60)
    
    # Initialize app state
    init_app_state(app)
    
    # Display module status
    logger.info("=" * 60)
    logger.info("📦 Module Status:")
    logger.info(f"  • Query Expansion: {'✅ Available' if app.state.QUERY_EXPANSION_AVAILABLE else '❌ Unavailable'}")
    logger.info(f"  • Reranker: {'✅ Available' if app.state.RERANKER_AVAILABLE else '❌ Unavailable'}")
    logger.info(f"  • Hybrid Retrieval: {'✅ Available' if getattr(app.state, 'HYBRID_RETRIEVAL_AVAILABLE', False) else '❌ Unavailable'}")
    
    # Build LLM status display - ensure clean formatting
    llm_available = getattr(app.state, 'LLM_AVAILABLE', False)
    llm_status = getattr(app.state, 'LLM_STATUS', 'Unknown')
    llm_model_name = getattr(app.state, 'LLM_MODEL_NAME', 'Unknown')
    
    if llm_available:
        llm_status_display = f"✅ Available ({llm_model_name})"
    else:
        # Ensure status message is clean and doesn't cause corruption
        status_msg = str(llm_status) if llm_status else "Unknown"
        llm_status_display = f"❌ {status_msg}"
    
    # Log with clean message - ensure single line output
    logger.info(f"  • LLM Model: {llm_status_display}")
    
    if not llm_available and app.state.MISTRAL_API_KEY:
        logger.info("  ℹ️  Note: LLM startup test failed, but service will still attempt LLM calls with retries on actual requests")
    logger.info("=" * 60)
    
    try:
        with engine.connect() as conn:
            # Basic DB connectivity check
            conn.execute(text("SELECT 1"))
            logger.info("✅ PostgreSQL connection successful")

            # Check required tables
            required_tables = ["user_queries", "query_responses", "sessions", "docs_chunks", "book_chunks"]
            tables_found = []
            tables_missing = []
            
            for table in required_tables:
                result = conn.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_name = :table_name
                        )
                    """),
                    {"table_name": table}
                )
                exists = result.scalar()
                if exists:
                    tables_found.append(table)
                else:
                    tables_missing.append(table)
                    # Auto-create critical tables if missing using SQLAlchemy models
                    model_cls = None
                    if table == "sessions":
                        model_cls = models.Session
                    elif table == "user_queries":
                        model_cls = models.UserQuery
                    elif table == "query_responses":
                        model_cls = models.QueryResponse

                    if model_cls is not None:
                        try:
                            model_cls.__table__.create(bind=engine, checkfirst=True)
                            logger.info(f"✅ Created table: {table}")
                            tables_found.append(table)
                            tables_missing.remove(table)
                        except Exception as e:
                            logger.error(f"❌ Failed to create table {table}: {e}")

            # Log table status in a single batch
            for table in tables_found:
                logger.info(f"✅ Table found: {table}")
            for table in tables_missing:
                logger.warning(f"⚠️  Table MISSING: {table}")

            # Migration: add chat_sessions.history sidebar (title, first_question)
            try:
                from src.db_service.migrations.add_chat_sessions_history_column import run_add_history_column
                run_add_history_column(engine)
            except Exception as hist_e:
                logger.error("❌ History column migration failed: %s", hist_e, exc_info=True)

            # Check extra tables and display connected or not in terminal
            extra_tables = ["chat_sessions", "chat_messages", "subscriptions", "file_uploads"]
            logger.info("📋 Tables status:")
            for table in extra_tables:
                result = conn.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_name = :table_name
                        )
                    """),
                    {"table_name": table}
                )
                exists = result.scalar()
                if exists:
                    logger.info(f"  ✅ Table connected: {table}")
                else:
                    logger.warning(f"  ⚠️  Table NOT connected: {table}")

            logger.info("🚀 Database check completed successfully")

    except Exception as e:
        logger.error("❌ DATABASE STARTUP CHECK FAILED")
        logger.error(str(e))
        app.state.DB_AVAILABLE = False
    
    # Initialize Search Service (BM25 Index)
    try:
        if app.state.DB_AVAILABLE:
            db = SessionLocal()
            try:
                get_search_service().initialize(db)
            finally:
                db.close()
    except Exception as e:
        logger.error(f"❌ Search Service initialization failed: {e}")

    # Mark startup as complete
    app.state._startup_complete = True
    
    # Startup complete
    yield
    
    # Shutdown
    logger.info("🛑 LLM User Service shutting down")


# -------------------------------------------------
# FASTAPI APP
# -------------------------------------------------
app = FastAPI(
    title="LLM User Service",
    description="Query and chat service for RAG system",
    lifespan=lifespan
)

# Global Exception Handlers
app.add_exception_handler(BaseAppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation Error", "errors": exc.errors()},
    )

# -------------------------------------------------
# FRONTEND (Templates + Static)
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "shared", "templates")
STATIC_DIR = settings.STATIC_DIR

# Create static directory if it doesn't exist
os.makedirs(STATIC_DIR, exist_ok=True)

templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)

# Auth Service Static
AUTH_STATIC_DIR = os.path.join(BASE_DIR, "auth_service", "static")
os.makedirs(AUTH_STATIC_DIR, exist_ok=True) # Ensure it exists
app.mount("/auth/static", StaticFiles(directory=AUTH_STATIC_DIR), name="auth_static")

# -------------------------------------------------
# INCLUDE ROUTERS
# -------------------------------------------------
# Include chat routes BEFORE admin so GET /api/user/sessions/history matches
# the chat history endpoint, not admin's GET /sessions/{session_id} (which would
# treat "history" as session_id and return 404).
# Only include with prefix to avoid duplicate Operation IDs (same route at /api/user/* and at root).
app.include_router(chat_routes.router, prefix="/api/user")
app.include_router(category_routes.router, prefix="/api/user")
app.include_router(history_search_routes.router, prefix="/api/user")


# Include main/admin routes (prefix only; root /health and /.well-known are in main.py below)
app.include_router(admin_routes.router, prefix="/api/user")

# Include ingestion routes
app.include_router(ingestion_routes.router, prefix="/api/user")

# Include auth and user routes
app.include_router(auth_routes.router, prefix="/api/auth", tags=["Auth"])
app.include_router(user_routes.router, prefix="/api/user", tags=["User"])

# Onboarding routes at /onboarding/*
app.include_router(onboarding_router)

# Include followup handling routes
from src.followup_service.api import followup_routes
app.include_router(followup_routes.router, prefix="/api", tags=["Follow-up"])
app.include_router(debug_router)

# Include hybrid retrieval routes (if router exists)
try:
    from src.vector_service.infrastructure.hybrid_retrieval import router as hybrid_retrieval_router
    app.include_router(hybrid_retrieval_router, prefix="/api")
    logger.info("✅ Hybrid retrieval router included")
except (ImportError, AttributeError) as e:
    logger.debug(f"Hybrid retrieval router not available: {e}")

from fastapi.responses import RedirectResponse
from src.shared.security import get_current_user_from_cookie
from typing import Optional

# -------------------------------------------------
# ROOT UI — login first, then chat
# -------------------------------------------------
@app.get("/")
def root_redirect(
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[str] = Depends(get_current_user_from_cookie)
):
    """Root URL: send to login if not authenticated, else to onboarding or chat."""
    if not user:
        return RedirectResponse(url="/api/auth/login", status_code=302)
    
    # Check onboarding status
    from src.auth_service.infrastructure.models import UserModel
    user_data = db.query(UserModel).filter(UserModel.email == user).first()
    
    if user_data and not user_data.profession:
        # New user -> Onboarding
        return RedirectResponse(url="/onboarding/welcome", status_code=302)
        
    return RedirectResponse(url="/chat", status_code=302)


@app.get("/chat", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[str] = Depends(get_current_user_from_cookie),
):
    """Serve the main dashboard UI. Requires login and onboarding."""
    if not user:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    from src.auth_service.infrastructure.models import UserModel
    user_data = db.query(UserModel).filter(UserModel.email == user).first()
    
    if not user_data:
        return RedirectResponse(url="/api/auth/login", status_code=302)
        
    # Force onboarding if incomplete
    if not user_data.profession:
        return RedirectResponse(url="/onboarding/welcome", status_code=302)

    name = user_data.full_name if getattr(user_data, "full_name", None) else "User"

    return templates.TemplateResponse(
        request,
        "index.html",
        {"user_name": name}
    )

# -------------------------------------------------
# HEALTH (Detailed Status for UI - at root level)
# -------------------------------------------------
@app.get("/health")
def health(request: Request):
    """Detailed health check endpoint for UI. Optimized for fast response."""
    state = request.app.state
    
    # Check database/vectorstore status - optimized for speed and resilience
    vectorstore_initialized = False
    database_connected = False
    
    # Use cached state if we just checked recently (< 10s) to avoid connection slot hogging
    last_check_time = getattr(state, '_last_db_check_time', 0)
    import time
    current_time = time.time()
    
    if current_time - last_check_time < 10 and hasattr(state, 'DB_AVAILABLE'):
        database_connected = state.DB_AVAILABLE
        vectorstore_initialized = getattr(state, 'VECTORSTORE_INITIALIZED', False)
    else:
        try:
            # Quick connection test (should be fast - uses connection pool)
            with engine.connect() as conn:
                # Simple connection test
                conn.execute(text("SELECT 1"))
                database_connected = True
                
                # Update state
                state._last_db_check_time = current_time
                
                # Quick table existence check (optimized query)
                result = conn.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'docs_chunks'
                        )
                    """)
                )
                vectorstore_initialized = result.scalar()
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            database_connected = False
            vectorstore_initialized = False
    
    # Update state cache for next request
    state.DB_AVAILABLE = database_connected
    state.VECTORSTORE_INITIALIZED = vectorstore_initialized
    
    # Determine overall status (do not mark degraded just because vectorstore is empty)
    status = "healthy" if database_connected else "degraded"
    
    return {
        "status": status,
        "app_name": settings.PROJECT_NAME,
        "app_version": settings.APP_VERSION if hasattr(settings, 'APP_VERSION') else "0.2.0",
        "vectorstore_initialized": vectorstore_initialized,
        "langchain_available": database_connected and vectorstore_initialized,
        "query_expansion_available": state.QUERY_EXPANSION_AVAILABLE,
        "query_expansion_strategies": getattr(state, "QUERY_EXPANSION_STRATEGIES", []),
        "reranking_available": state.RERANKER_AVAILABLE,
        "reranker_types": getattr(state, "RERANKER_TYPES", []),
        "hybrid_retrieval_available": getattr(state, "HYBRID_RETRIEVAL_AVAILABLE", False),
        "database_connected": database_connected,
        "llm_configured": bool(settings.MISTRAL_API_KEY),
        "llm_available": getattr(state, "LLM_AVAILABLE", False),
        "llm_model": getattr(state, "LLM_MODEL_NAME", settings.MISTRAL_MODEL),
        "llm_status": getattr(state, "LLM_STATUS", "Unknown")
    }


# -------------------------------------------------
# HISTORY
# -------------------------------------------------
@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, user: Optional[str] = Depends(get_current_user_from_cookie)):
    """Serve history page."""
    if not user:
        return RedirectResponse(url="/api/auth/login", status_code=302)

    return templates.TemplateResponse(
        request,
        "history.html",
    )

@app.get("/debug-retrieval", response_class=HTMLResponse)
def debug_retrieval_page(request: Request, user: Optional[str] = Depends(get_current_user_from_cookie)):
    """Serve raw retrieval debug page."""
    if not user:
        return RedirectResponse(url="/api/auth/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "debug_retrieval.html",
    )

@app.get("/api/user/history")
def history_api(db: Session = Depends(get_db)):
    """Get recent query history with KB/LLM contributions and statistics."""
    from sqlalchemy import func, distinct
    from datetime import datetime, timedelta

    # Show last 7 days so query_responses data displays (was 24h only)
    history_hours = 24 * 7  # 168 hours = 7 days
    cutoff_time = datetime.utcnow() - timedelta(hours=history_hours)

    queries = (
        db.query(models.UserQuery)
        .filter(models.UserQuery.created_at >= cutoff_time)
        .order_by(models.UserQuery.created_at.desc())
        .limit(500)
        .all()
    )

    # Calculate statistics (same window)
    total_queries = db.query(func.count(models.UserQuery.id)).filter(
        models.UserQuery.created_at >= cutoff_time
    ).scalar() or 0

    total_responses = db.query(func.count(models.QueryResponse.id)).filter(
        models.QueryResponse.created_at >= cutoff_time
    ).scalar() or 0
    
    # Get total KB chunks (aggregated from new tables)
    docs_chunks_count = db.query(func.count(models.DocsChunk.id)).scalar() or 0
    book_chunks_count = db.query(func.count(models.BookChunk.id)).scalar() or 0
    total_kb_chunks = docs_chunks_count + book_chunks_count
    
    # Get unique KB files
    docs_files = db.query(func.count(func.distinct(models.DocsChunk.source_file))).scalar() or 0
    book_files = db.query(func.count(func.distinct(models.BookChunk.source_file))).scalar() or 0
    kb_files = docs_files + book_files
    
    # Build query history with contributions
    query_history = []
    for query in queries:
        # Get response for this query
        response = (
            db.query(models.QueryResponse)
            .filter(models.QueryResponse.query_id == query.id)
            .first()
        )
        
        if not response:
            continue
        
        # Get retrieved chunks (using prefix-based resolution)
        chunk_ids = response.retrieved_context_ids or []
        chunks = []
        if chunk_ids:
            for uid in chunk_ids:
                chunk = crud.get_unified_chunk(db, uid)
                if chunk:
                    chunks.append(chunk)
        
        # Calculate KB contribution
        kb_context_length = sum(len(chunk.get("text", "") or "") for chunk in chunks)
        kb_chunks_count = len(chunks)
        kb_sources = list(set([chunk["metadata"].get("source_file") or chunk["metadata"].get("domain") 
                              for chunk in chunks if chunk.get("metadata")]))
        
        # Get LLM contribution from response metadata
        response_metadata = response.response_metadata or {}
        prompt_tokens = response_metadata.get("prompt_tokens") or 0
        completion_tokens = response_metadata.get("completion_tokens") or 0
        total_tokens = response_metadata.get("total_tokens") or (prompt_tokens + completion_tokens)
        llm_response_length = len(response.response_text or "")
        
        # Calculate REAL percentages (KB vs LLM) based on character counts
        total_chars = kb_context_length + llm_response_length
        if total_chars > 0:
            kb_percentage = (kb_context_length / total_chars) * 100
            llm_percentage = (llm_response_length / total_chars) * 100
        else:
            # Fallback if both are empty
            kb_percentage = 0.0
            llm_percentage = 0.0
        
        query_history.append({
            "id": query.id,
            "question": query.query_text,
            "answer": response.response_text,
            "timestamp": query.created_at.isoformat(),
            "kb_contribution": {
                "percentage": float(f"{kb_percentage:.1f}"),
                "chunks_count": kb_chunks_count,
                "context_chars": kb_context_length,
                "sources": kb_sources
            },
            "llm_contribution": {
                "percentage": float(f"{llm_percentage:.1f}"),
                "response_chars": llm_response_length,
                "total_tokens": total_tokens,
                "model": response.llm_model or "Unknown"
            }
        })
    
    return {
        "statistics": {
            "total_queries": total_queries,
            "total_kb_chunks": total_kb_chunks,
            "kb_files": kb_files,
            "total_responses": total_responses
        },
        "queries": query_history
    }


@app.get("/api/metrics/performance")
def metrics_performance(request: Request):
    """Return lightweight performance metrics derived from DB and app state.

    This endpoint is intentionally inexpensive and provides aggregated counts
    used by the monitor UI. It uses length(response_text) as a proxy for
    completion tokens when token counts are not available.
    """
    CHAR_PER_TOKEN = 4.0
    
    try:
        with engine.connect() as conn:
            total_res = int(conn.execute(text("SELECT COUNT(1) FROM query_responses")).scalar() or 0)
            total_chars = int(conn.execute(text("SELECT COALESCE(SUM(COALESCE(LENGTH(response_text),0)),0) FROM query_responses")).scalar() or 0)
            avg_latency_ms = float(conn.execute(text("SELECT COALESCE(AVG(latency_ms),0) FROM query_responses")).scalar() or 0)
            responses_with_context = int(conn.execute(text("SELECT COUNT(1) FROM query_responses WHERE COALESCE(cardinality(retrieved_context_ids),0) > 0")).scalar() or 0)

            completion_tokens = int(total_chars / CHAR_PER_TOKEN) if total_chars > 0 else 0
            prompt_tokens = 0

            # KB percentage: responses that retrieved context
            accuracy_estimate = (responses_with_context / total_res) if total_res > 0 else 0

            performance = {
                "requests_total": total_res,
                "average_latency": (avg_latency_ms / 1000.0) if avg_latency_ms is not None else 0,
                "accuracy_estimate": accuracy_estimate,  # % of requests using KB context
                "token_totals": {"prompt": prompt_tokens, "completion": completion_tokens},  # LLM tokens
                "requests_with_context": responses_with_context,
                "cache_summary": request.app.state.response_cache.summary() if hasattr(request.app.state, 'response_cache') else {"entries": 0},
                "token_history": [],
                "latency_history": [],
                "accuracy_history": []
            }
    except Exception as e:
        logger.warning(f"Error fetching performance metrics: {e}")
        performance = {
            "requests_total": 0,
            "average_latency": 0,
            "accuracy_estimate": 0,
            "token_totals": {"prompt": 0, "completion": 0},
            "requests_with_context": 0,
            "cache_summary": {"entries": 0},
            "token_history": [],
            "latency_history": [],
            "accuracy_history": []
        }

    return performance

