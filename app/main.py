"""
LLM User Service - Main Application
Handles user queries, RAG pipeline, and responses.
"""

from contextlib import asynccontextmanager
import os
import logging

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text, desc
from datetime import datetime, timedelta
import platform
import time

from app.database import engine
from app import models
from app.routes import main as main_routes
from app.routes import chat as chat_routes  

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fintax")

# -------------------------------------------------
# GLOBAL API PREFIX (✅ SINGLE PLACE)
# -------------------------------------------------
API_PREFIX = "/api/user"

# -------------------------------------------------
# APP STATE INITIALIZATION
# -------------------------------------------------
def init_app_state(app: FastAPI):
    app.state.DB_AVAILABLE = True

    # Query expansion
    app.state.QUERY_EXPANSION_AVAILABLE = False
    try:
        from app.query_expansion.tax_vocabulary import expand_query
        expand_query("test")
        app.state.QUERY_EXPANSION_AVAILABLE = True
    except Exception:
        pass

    # Reranker
    app.state.RERANKER_AVAILABLE = False
    try:
        from sentence_transformers import CrossEncoder
        CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
        app.state.RERANKER_AVAILABLE = True
    except Exception:
        pass

    # LLM config
    app.state.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    app.state.OPENROUTER_MODEL = os.getenv(
        "OPENROUTER_MODEL", "openai/gpt-3.5-turbo"
    )

# -------------------------------------------------
# APP LIFESPAN
# -------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 LLM User Service starting")

    init_app_state(app)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✅ PostgreSQL connected")
    except Exception as e:
        print("❌ DB connection failed:", e)
        app.state.DB_AVAILABLE = False

    yield
    print("🛑 LLM User Service shutting down")

# -------------------------------------------------
# FASTAPI APP
# -------------------------------------------------
app = FastAPI(
    title="LLM User Service",
    description="Query and chat service for RAG system",
    lifespan=lifespan,
)

# -------------------------------------------------
# FRONTEND (Templates + Static)
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "../static")

os.makedirs(STATIC_DIR, exist_ok=True)

templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# -------------------------------------------------
# INCLUDE ROUTERS (✅ PREFIX APPLIED ONCE)
# -------------------------------------------------
app.include_router(main_routes.router, prefix=API_PREFIX)
app.include_router(chat_routes.router, prefix=API_PREFIX)

# -------------------------------------------------
# UI ROUTES (NO PREFIX)
# -------------------------------------------------
@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect root to the UI chat page."""
    return RedirectResponse(url=f"{API_PREFIX}/ui/chat")


@app.get(f"{API_PREFIX}/ui/chat", response_class=HTMLResponse)
def ui_chat(request: Request):
    """Return the chat UI HTML page.

    This endpoint serves the front-end chat interface and must return HTML only.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get(f"{API_PREFIX}/ui/history", response_class=HTMLResponse)
def ui_history(request: Request):
    """Return the history UI HTML page."""
    return templates.TemplateResponse("history.html", {"request": request})


@app.get("/monitor", include_in_schema=False, response_class=HTMLResponse)
@app.get(f"{API_PREFIX}/monitor", include_in_schema=False, response_class=HTMLResponse)
def monitor_ui(request: Request):
    """Serve the performance monitoring UI (monitor.html)."""
    return templates.TemplateResponse("monitor.html", {"request": request})


@app.get(f"{API_PREFIX}/ui/monitor", include_in_schema=False, response_class=HTMLResponse)
def ui_monitor_namespaced(request: Request):
    """Serve the monitoring UI under the namespaced UI path as well."""
    return templates.TemplateResponse("monitor.html", {"request": request})


# -----------------------------
# Lightweight monitoring APIs
# -----------------------------
@app.get("/api/metrics/system")
@app.get(f"{API_PREFIX}/metrics/system")
def metrics_system():
    """Return very small realtime system metrics. Uses psutil when available, else fallbacks."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        virtual = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()

        return {
            "latest": {
                "cpu": cpu,
                "memory": virtual.percent,
                "disk": disk.percent,
                "network": {
                    "upload_kbps": (net.bytes_sent / 1024.0),
                    "download_kbps": (net.bytes_recv / 1024.0)
                }
            },
            "psutil_available": True
        }
    except Exception:
        # Safe fallback for environments without psutil
        return {
            "latest": {"cpu": 0, "memory": 0, "disk": 0, "network": {"upload_kbps": 0, "download_kbps": 0}},
            "psutil_available": False
        }


@app.get("/api/metrics/system-info")
@app.get(f"{API_PREFIX}/metrics/system-info")
def metrics_system_info():
    """Return static system info useful to the monitor UI."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)
        uptime = int(time.time() - psutil.boot_time())
    except Exception:
        mem = None
        disk = None
        cpu_count_logical = None
        cpu_count_physical = None
        uptime = None

    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "cpu_count_logical": cpu_count_logical,
        "cpu_count_physical": cpu_count_physical,
        "memory_total": getattr(mem, 'total', None),
        "memory_used": getattr(mem, 'used', None),
        "memory_percent": getattr(mem, 'percent', None),
        "disk_total": getattr(disk, 'total', None),
        "disk_used": getattr(disk, 'used', None),
        "disk_percent": getattr(disk, 'percent', None),
        "uptime": uptime,
        "python_version": platform.python_version(),
    }


@app.get("/api/metrics/performance")
@app.get(f"{API_PREFIX}/metrics/performance")
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

            accuracy_estimate = (responses_with_context / total_res) if total_res > 0 else 0

            performance = {
                "requests_total": total_res,
                "average_latency": (avg_latency_ms / 1000.0) if avg_latency_ms is not None else 0,
                "accuracy_estimate": accuracy_estimate,
                "token_totals": {"prompt": prompt_tokens, "completion": completion_tokens},
                "requests_with_context": responses_with_context,
                "cache_summary": request.app.state.response_cache.summary() if hasattr(request.app.state, 'response_cache') else {"entries": 0},
                "token_history": [],
                "latency_history": [],
                "accuracy_history": []
            }
    except Exception:
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

# -------------------------------------------------
# API: HEALTH  → /api/user/health
# -------------------------------------------------
@app.get("/health")
@app.get(f"{API_PREFIX}/health")
def health(request: Request):
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
            vectorstore_initialized = result.scalar()
    except Exception as e:
        logger.warning(f"DB check failed: {e}")

    status = "healthy" if database_connected else "degraded"

    return {
        "status": status,
        "database_connected": database_connected,
        "vectorstore_initialized": vectorstore_initialized,
        "langchain_available": vectorstore_initialized,
        "query_expansion_available": state.QUERY_EXPANSION_AVAILABLE,
        "reranking_available": state.RERANKER_AVAILABLE,
        "llm_configured": bool(state.OPENROUTER_API_KEY),
    }

# -------------------------------------------------
# NOTE: history API moved to `app.routes.main` so it is
# provided via APIRouter and automatically namespaced
# under the `/api/user` prefix.
