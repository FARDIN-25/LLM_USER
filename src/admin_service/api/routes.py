"""
Main routes - home, health, diagnostics (FastAPI).
"""

from fastapi import APIRouter, Request, Depends, Body, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional
import logging
import uuid
import platform
import time
import requests
from datetime import datetime

from src.db_service.database import get_db
from src.db_service import models, crud
from src.shared import schemas, settings
from src.shared.monitoring import monitoring

logger = logging.getLogger("fintax")

router = APIRouter(tags=["Main"])


@router.get("/info")
def api_info():
    """
    API info endpoint.
    """
    return {
        "service": "LLM User Service",
        "status": "running",
        "description": "Query and chat service for RAG system"
    }
@router.get("/upload-limits")
def upload_limits():
    """Return upload limits used by the UI."""
    return {
        "max_files_per_request": 100,
        "max_content_length_mb": 1024,
        "allowed_types": [".pdf", ".txt", ".docx", ".csv", ".xlsx"]
    }

@router.get("/diagnostics")
def diagnostics(request: Request):
    """
    Diagnostics endpoint for debugging.
    """
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
            "database": {
                "connected": state.DB_AVAILABLE,
                "type": "PostgreSQL (pgvector)",
            },
            "reranker": {
                "available": state.RERANKER_AVAILABLE,
            },
            "query_expansion": {
                "available": state.QUERY_EXPANSION_AVAILABLE,
            },
            "llm": {
                "provider": "MISTRAL",
                "model": state.MISTRAL_MODEL,
            },
        },
        "cache": state.response_cache.summary()
        if hasattr(state, "response_cache") else {},
    }

    return diag


@router.get("/monitoring/metrics")
def get_monitoring_metrics():
    """Get all monitoring metrics."""
    return monitoring.get_metrics()


@router.get("/monitoring/memory")
def get_memory_from_db(db: Session = Depends(get_db)):
    """Get memory (queries and answers) from database - persists across server restarts."""
    from sqlalchemy import desc
    from datetime import datetime, timedelta
    
    try:
        # Get recent queries with their responses (last 24 hours, limit 100)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        queries = (
            db.query(models.UserQuery)
            .filter(models.UserQuery.created_at >= cutoff_time)
            .order_by(desc(models.UserQuery.created_at))
            .limit(100)
            .all()
        )
        
        memory_items = []
        for query in queries:
            # Get response for this query
            response = (
                db.query(models.QueryResponse)
                .filter(models.QueryResponse.query_id == query.id)
                .first()
            )
            
            if response:
                # Get token info from response metadata
                response_metadata = response.response_metadata or {}
                prompt_tokens = response_metadata.get("prompt_tokens", 0) or 0
                completion_tokens = response_metadata.get("completion_tokens", 0) or 0
                source_names = response_metadata.get("source_names", []) or []
                
                # Ensure session_id is always present - use query session_id or generate one
                session_id = query.session_id
                if not session_id or session_id.strip() == "":
                    # Generate a session ID from query timestamp if missing
                    import uuid
                    date_str = query.created_at.strftime("%d%m%Y")
                    short_uuid = str(uuid.uuid4())[:8]
                    session_id = f"{date_str}-{short_uuid}"
                
                memory_items.append({
                    "timestamp": query.created_at.isoformat(),
                    "query": query.query_text or "",
                    "response": response.response_text or "",
                    "session_id": session_id,
                    "llm_model": response.llm_model or "Unknown",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "source_names": source_names
                })
        
        return memory_items
    except Exception as e:
        logger.error(f"Error loading memory from database: {e}", exc_info=True)
        # Return in-memory memory as fallback
        return list(monitoring.memory)


@router.get("/monitoring/resources")
def get_resources_info(db: Session = Depends(get_db)):
    """Get information about knowledge base resources."""
    # Query the database for actual counts (aggregated from both tables)
    docs_count = db.query(models.DocsChunk).count()
    book_count = db.query(models.BookChunk).count()
    total_chunks = docs_count + book_count
    
    # Count files and types from both tables
    docs_files = db.query(
        models.DocsChunk.file_type,
        func.count(func.distinct(models.DocsChunk.source_file))
    ).group_by(models.DocsChunk.file_type).all()
    
    book_files = db.query(
        func.count(func.distinct(models.BookChunk.source_file))
    ).scalar() or 0
    
    file_types = {ftype: count for ftype, count in docs_files}
    if book_files > 0:
        file_types["pdf"] = file_types.get("pdf", 0) + book_files # Assuming books are PDF
        
    total_files = sum(file_types.values())
    
    # Get KB source names and chunk counts
    docs_sources = db.query(
        models.DocsChunk.domain,
        func.count(models.DocsChunk.id)
    ).group_by(models.DocsChunk.domain).all()
    
    kb_source_names = {source: count for source, count in docs_sources}
    if book_count > 0:
        kb_source_names["Books"] = book_count
    
    monitoring.update_resources(
        total_chunks=total_chunks,
        total_files=total_files,
        file_types=file_types,
        kb_source_names=kb_source_names
    )
    return monitoring.resources.copy()


@router.post("/monitoring/rag-settings")
def update_rag_settings(settings: Dict = Body(...)):
    """Update RAG settings."""
    monitoring.update_rag_settings(**settings)
    return {"status": "updated", "settings": monitoring.rag_settings.copy()}


@router.post("/monitoring/model-settings")
def update_model_settings(settings: Dict = Body(...)):
    """Update model settings."""
    monitoring.update_model_settings(**settings)
    return {"status": "updated", "settings": monitoring.model_settings.copy()}


@router.get("/monitoring/response-log")
def get_response_log(db: Session = Depends(get_db), limit: int = 20):
    """Get recent query responses from the database."""
    from sqlalchemy import desc
    from datetime import datetime, timedelta
    
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    responses = (
        db.query(models.QueryResponse)
        .filter(models.QueryResponse.created_at >= cutoff_time)
        .order_by(desc(models.QueryResponse.created_at))
        .limit(limit)
        .all()
    )
    
    return [
        {
            "id": r.id,
            "query_id": r.query_id,
            "response_text": r.response_text,
            "llm_model": r.llm_model,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat(),
            "prompt_tokens": r.response_metadata.get("prompt_tokens") if r.response_metadata else None,
            "completion_tokens": r.response_metadata.get("completion_tokens") if r.response_metadata else None,
            "total_tokens": r.response_metadata.get("total_tokens") if r.response_metadata else None
        }
        for r in responses
    ]


@router.post("/session/track", response_model=schemas.SessionOut)
def track_session_endpoint(data: schemas.SessionIn, db: Session = Depends(get_db)):
    """Track a session and update its activity."""
    from src.auth_service.application.session_service import track_session as track_session_service
    
    s = track_session_service(db, data.session_id)
    return {
        "session_id": s.session_id,
        "created_at": s.created_at.strftime("%d/%m/%Y %I:%M:%S %p"),
        "last_activity_at": s.last_activity_at.strftime("%d/%m/%Y %I:%M:%S %p"),
        "query_count": s.query_count
    }


@router.get("/session/list")
def list_sessions(db: Session = Depends(get_db)):
    """List all sessions ordered by last activity."""
    sessions = (
        db.query(models.Session)
        .order_by(models.Session.last_activity_at.desc())
        .all()
    )
    
    return [
        {
            "session_id": s.session_id,
            "created_at": s.created_at.strftime("%d/%m/%Y %I:%M:%S %p"),
            "last_activity_at": s.last_activity_at.strftime("%d/%m/%Y %I:%M:%S %p"),
            "query_count": s.query_count
        }
        for s in sessions
    ]


@router.get("/monitoring/sessions")
def get_sessions_info(db: Session = Depends(get_db)):
    """Get session information with accurate query counts from database."""
    from sqlalchemy import desc, inspect
    from datetime import datetime, timedelta
    
    # Check if sessions table exists
    inspector = inspect(db.bind)
    table_exists = "sessions" in inspector.get_table_names()
    
    if not table_exists:
        # Create table if it doesn't exist
        try:
            from src.db_service.models import Session
            Session.__table__.create(bind=db.bind, checkfirst=True)
        except Exception as e:
            logger.warning(f"Could not create sessions table: {e}")
            # Return empty dict if table creation fails
            return {}
    
    # Get sessions from database
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    try:
        sessions = (
            db.query(models.Session)
            .filter(models.Session.last_activity_at >= cutoff_time)
            .order_by(desc(models.Session.last_activity_at))
            .all()
        )
    except Exception as e:
        logger.warning(f"Error querying sessions table: {e}")
        # Return empty dict on error
        return {}
    
    # Convert to dictionary format - ensure query_count is properly read
    sessions_dict = {}
    for s in sessions:
        # Get query_count directly from database (no refresh needed as we just queried)
        query_count = int(s.query_count) if s.query_count is not None else 0
        sessions_dict[s.session_id] = {
            "created_at": s.created_at.isoformat(),
            "last_activity": s.last_activity_at.isoformat(),
            "last_activity_at": s.last_activity_at.isoformat(),
            "query_count": query_count
        }
    
    # Merge with in-memory active sessions for backward compatibility
    in_memory_sessions = monitoring.active_sessions.copy()
    for session_id, session_data in in_memory_sessions.items():
        if session_id not in sessions_dict:
            sessions_dict[session_id] = session_data
    
    return sessions_dict


@router.get("/endpoints-status")
def get_endpoints_status(request: Request):
    """Get status of all API endpoints for User Service, Cleaning Service, and Ingestion Service."""
    # Get service URLs from settings
    cleaning_service_url = settings.CLEANING_SERVICE_URL
    ingestion_service_url = settings.INGESTION_SERVICE_URL
    base_url = str(request.base_url).rstrip('/')
    app = request.app
    
    # User Service endpoints
    user_service_endpoints = [
        {"name": "Info", "path": "/api/info", "method": "GET", "service": "user"},
        {"name": "Health", "path": "/api/health", "method": "GET", "service": "user"},
        {"name": "Diagnostics", "path": "/api/diagnostics", "method": "GET", "service": "user"},
        {"name": "Storage Status", "path": "/api/storage-status", "method": "GET", "service": "user"},
        {"name": "Upload Limits", "path": "/api/upload-limits", "method": "GET", "service": "user"},
        {"name": "Monitoring Metrics", "path": "/api/monitoring/metrics", "method": "GET", "service": "user"},
        {"name": "Monitoring Resources", "path": "/api/monitoring/resources", "method": "GET", "service": "user"},
        {"name": "Monitoring Response Log", "path": "/api/monitoring/response-log", "method": "GET", "service": "user"},
        {"name": "Chat", "path": "/chat", "method": "POST", "service": "user"},
        {"name": "Query", "path": "/query", "method": "POST", "service": "user"},
    ]
    
    # Cleaning Service endpoints
    cleaning_service_endpoints = [
        {"name": "Health", "path": "/health", "method": "GET", "service": "cleaning"},
        {"name": "Info", "path": "/api/info", "method": "GET", "service": "cleaning"},
        {"name": "Status", "path": "/api/status", "method": "GET", "service": "cleaning"},
        {"name": "Process", "path": "/api/process", "method": "POST", "service": "cleaning"},
    ]
    
    # Ingestion Service endpoints
    ingestion_service_endpoints = [
        {"name": "Health", "path": "/api/health", "method": "GET", "service": "ingestion"},
        {"name": "Info", "path": "/api/info", "method": "GET", "service": "ingestion"},
        {"name": "Diagnostics", "path": "/api/diagnostics", "method": "GET", "service": "ingestion"},
        {"name": "Upload CSV", "path": "/upload/csv", "method": "POST", "service": "ingestion"},
        {"name": "Ingest CSV", "path": "/admin/ingest-csv", "method": "POST", "service": "ingestion"},
        {"name": "Ingested Sources", "path": "/admin/ingested-sources", "method": "GET", "service": "ingestion"},
    ]
    
    endpoints = user_service_endpoints + cleaning_service_endpoints + ingestion_service_endpoints
    
    results = []
    
    # Check if routes exist in the app
    app_routes = {}
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                if method != 'HEAD':  # Skip HEAD method
                    key = f"{method}:{route.path}"
                    app_routes[key] = route.path
    
    for endpoint in endpoints:
        status = "unknown"
        response_time_ms = None
        error = None
        service = endpoint.get("service", "user")
        
        try:
            # Determine which service URL to use
            if service == "cleaning":
                service_base_url = cleaning_service_url
            elif service == "ingestion":
                service_base_url = ingestion_service_url
            else:  # user service
                service_base_url = base_url
            
            # For user service, check if route exists in FastAPI app
            if service == "user":
                route_key = f"{endpoint['method']}:{endpoint['path']}"
                route_exists = route_key in app_routes
                
                if not route_exists:
                    # Try alternative paths
                    alt_paths = [
                        endpoint['path'].replace('/api/', '/api/user/'),
                        endpoint['path'].replace('/api/user/', '/api/'),
                    ]
                    for alt_path in alt_paths:
                        alt_key = f"{endpoint['method']}:{alt_path}"
                        if alt_key in app_routes:
                            route_exists = True
                            break
                
                if endpoint['method'] == 'GET' and route_exists:
                    # For GET requests, try to fetch
                    start_time = time.time()
                    try:
                        url = f"{service_base_url}{endpoint['path']}"
                        resp = requests.get(url, timeout=3, allow_redirects=True)
                        response_time_ms = int((time.time() - start_time) * 1000)
                        if resp.status_code == 200:
                            status = "online"
                        elif resp.status_code < 500:
                            status = "degraded"
                            error = f"HTTP {resp.status_code}"
                        else:
                            status = "error"
                            error = f"HTTP {resp.status_code}"
                    except requests.exceptions.Timeout:
                        status = "timeout"
                        error = "Request timeout"
                    except requests.exceptions.ConnectionError:
                        status = "offline"
                        error = "Connection error"
                    except Exception as e:
                        status = "error"
                        error = str(e)[:50]
                elif route_exists:
                    # For POST requests, mark as available if route exists
                    status = "available"
                    response_time_ms = 0
                else:
                    status = "offline"
                    error = "Route not found"
            else:
                # For Cleaning and Ingestion services, make HTTP requests
                if endpoint['method'] == 'GET':
                    start_time = time.time()
                    try:
                        url = f"{service_base_url}{endpoint['path']}"
                        resp = requests.get(url, timeout=3, allow_redirects=True)
                        response_time_ms = int((time.time() - start_time) * 1000)
                        if resp.status_code == 200:
                            status = "online"
                        elif resp.status_code < 500:
                            status = "degraded"
                            error = f"HTTP {resp.status_code}"
                        else:
                            status = "error"
                            error = f"HTTP {resp.status_code}"
                    except requests.exceptions.Timeout:
                        status = "timeout"
                        error = "Request timeout"
                    except requests.exceptions.ConnectionError:
                        status = "offline"
                        error = "Connection error"
                    except Exception as e:
                        status = "error"
                        error = str(e)[:50]
                else:  # POST
                    # For POST endpoints, try to check if service is reachable via health endpoint
                    try:
                        health_url = f"{service_base_url}/health" if service == "cleaning" else f"{service_base_url}/api/health"
                        health_resp = requests.get(health_url, timeout=2, allow_redirects=True)
                        if health_resp.status_code == 200:
                            status = "available"
                            response_time_ms = 0
                        else:
                            status = "degraded"
                            error = f"Service reachable but health check failed"
                    except:
                        status = "offline"
                        error = "Service unreachable"
        
        except Exception as e:
            status = "error"
            error = str(e)[:50]
            logger.warning(f"Error checking endpoint {endpoint['name']} ({service}): {e}")
        
        results.append({
            "name": endpoint["name"],
            "path": endpoint["path"],
            "method": endpoint["method"],
            "status": status,
            "response_time_ms": response_time_ms,
            "error": error,
            "service": service,
            "running": status in ["online", "available"]
        })
    
    # Calculate overall status per service
    user_endpoints = [r for r in results if r.get("service") == "user"]
    cleaning_endpoints = [r for r in results if r.get("service") == "cleaning"]
    ingestion_endpoints = [r for r in results if r.get("service") == "ingestion"]
    
    def calculate_service_status(service_results):
        online_count = sum(1 for r in service_results if r["status"] in ["online", "available"])
        total_count = len(service_results)
        if total_count == 0:
            return "unknown", 0, 0
        overall_status = "healthy" if online_count == total_count else "degraded" if online_count > 0 else "offline"
        return overall_status, online_count, total_count
    
    user_status, user_online, user_total = calculate_service_status(user_endpoints)
    cleaning_status, cleaning_online, cleaning_total = calculate_service_status(cleaning_endpoints)
    ingestion_status, ingestion_online, ingestion_total = calculate_service_status(ingestion_endpoints)
    
    # Overall status across all services
    total_online = user_online + cleaning_online + ingestion_online
    total_count = user_total + cleaning_total + ingestion_total
    overall_status = "healthy" if total_online == total_count else "degraded" if total_online > 0 else "offline"
    
    return {
        "overall_status": overall_status,
        "online_count": total_online,
        "total_count": total_count,
        "services": {
            "user": {
                "status": user_status,
                "online_count": user_online,
                "total_count": user_total,
                "endpoints": user_endpoints
            },
            "cleaning": {
                "status": cleaning_status,
                "online_count": cleaning_online,
                "total_count": cleaning_total,
                "endpoints": cleaning_endpoints
            },
            "ingestion": {
                "status": ingestion_status,
                "online_count": ingestion_online,
                "total_count": ingestion_total,
                "endpoints": ingestion_endpoints
            }
        },
        "endpoints": results,  # Keep for backward compatibility
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# =============================================================================
# ChatSession, ChatMessage, Subscription, FileUpload
# =============================================================================

@router.post("/sessions", response_model=schemas.ChatSessionOut)
def create_session(data: schemas.ChatSessionCreate, db: Session = Depends(get_db)):
    """Create a new chat session. If session_id is omitted, a UUID is generated."""
    session_id = data.session_id or str(uuid.uuid4())
    existing = crud.get_chat_session_by_session_id(db, session_id)
    if existing:
        raise HTTPException(status_code=409, detail="Session with this session_id already exists")
    chat_session = crud.create_chat_session(db, data, session_id=session_id)
    return chat_session


@router.get("/sessions/{session_id}", response_model=schemas.ChatSessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get a chat session by session_id."""
    chat = crud.get_chat_session_by_session_id(db, session_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@router.get("/sessions", response_model=list[schemas.ChatSessionOut])
def list_sessions_by_user(
    user_id: str = Query(..., description="User ID to list sessions for"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List chat sessions for a user, ordered by updated_at descending."""
    return crud.get_chat_sessions_by_user(db, user_id, limit=limit)


@router.patch("/sessions/{session_id}", response_model=schemas.ChatSessionOut)
def update_session(session_id: str, data: schemas.ChatSessionUpdate, db: Session = Depends(get_db)):
    """Update a chat session."""
    chat = crud.update_chat_session(db, session_id, data)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@router.patch("/sessions", response_model=schemas.ChatSessionOut)
def update_session_by_body(data: schemas.ChatSessionUpdateWithId, db: Session = Depends(get_db)):
    """Update a chat session by session_id in body."""
    chat = crud.update_chat_session(db, data.session_id, schemas.ChatSessionUpdate())
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a chat session and its messages (cascade)."""
    if not crud.delete_chat_session(db, session_id):
        raise HTTPException(status_code=404, detail="Chat session not found")
    return None


@router.post("/messages", response_model=schemas.ChatMessageOut)
def create_message(data: schemas.ChatMessageCreate, db: Session = Depends(get_db)):
    """Create a chat message linking a query and response. Session must exist."""
    chat = crud.get_chat_session_by_session_id(db, data.session_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if not crud.get_query_by_id(db, data.query_id):
        raise HTTPException(status_code=404, detail="Query not found")
    if not crud.get_response_by_id(db, data.response_id):
        raise HTTPException(status_code=404, detail="Response not found")
    return crud.create_chat_message(db, data)


@router.get("/messages/{message_id}", response_model=schemas.ChatMessageOut)
def get_message(message_id: int, db: Session = Depends(get_db)):
    """Get a chat message by ID."""
    msg = crud.get_chat_message_by_id(db, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Chat message not found")
    return msg


@router.get("/messages", response_model=list[schemas.ChatMessageOut])
def list_messages_by_session(
    session_id: str = Query(..., description="Session ID"),
    favourites_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List messages in a session, optionally only favourites."""
    return crud.get_chat_messages_by_session(db, session_id, favourites_only=favourites_only, limit=limit)


@router.patch("/messages/{message_id}", response_model=schemas.ChatMessageOut)
def update_message(
    message_id: int, 
    data: schemas.ChatMessageUpdate, 
    db: Session = Depends(get_db),
    user_id: Optional[str] = Query(None, description="Optional: User ID for authorization check")
):
    """
    Update message (react, tags, feedback).
    If user_id is provided, verifies message ownership.
    Admin endpoints can update any message without user_id.
    """
    # If user_id provided, verify ownership
    if user_id:
        if not crud.verify_message_ownership(db, message_id, user_id):
            raise HTTPException(status_code=403, detail="You can only update your own messages.")
    
    msg = crud.update_chat_message(db, message_id, data)
    if not msg:
        raise HTTPException(status_code=404, detail="Chat message not found")
    return msg


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: int, db: Session = Depends(get_db)):
    """Delete a chat message."""
    if not crud.delete_chat_message(db, message_id):
        raise HTTPException(status_code=404, detail="Chat message not found")
    return None


@router.post("/subscriptions", response_model=schemas.SubscriptionOut)
def create_subscription(data: schemas.SubscriptionCreate, db: Session = Depends(get_db)):
    """Create a subscription for a user. Fails if user already has a subscription."""
    existing = crud.get_subscription_by_user(db, data.user_id)
    if existing:
        raise HTTPException(status_code=409, detail="User already has a subscription")
    return crud.create_subscription(db, data)


@router.get("/subscriptions/{user_id}", response_model=schemas.SubscriptionOut)
def get_subscription(user_id: str, db: Session = Depends(get_db)):
    """Get subscription by user_id."""
    sub = crud.get_subscription_by_user(db, user_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.patch("/subscriptions/{user_id}", response_model=schemas.SubscriptionOut)
def update_subscription(user_id: str, data: schemas.SubscriptionUpdate, db: Session = Depends(get_db)):
    """Update subscription (plan_type, features, usage_limits, expires_at)."""
    sub = crud.update_subscription(db, user_id, data)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.delete("/subscriptions/{user_id}", status_code=204)
def delete_subscription(user_id: str, db: Session = Depends(get_db)):
    """Delete subscription for a user."""
    if not crud.delete_subscription(db, user_id):
        raise HTTPException(status_code=404, detail="Subscription not found")
    return None


@router.post("/files", response_model=schemas.FileUploadOut)
def create_file_upload(data: schemas.FileUploadCreate, db: Session = Depends(get_db)):
    """Record a file upload. Optionally link to a chat session."""
    if data.session_id:
        chat = crud.get_chat_session_by_session_id(db, data.session_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")
    return crud.create_file_upload(db, data)


@router.get("/files/{file_id}", response_model=schemas.FileUploadOut)
def get_file_upload(file_id: int, db: Session = Depends(get_db)):
    """Get a file upload record by ID."""
    fu = crud.get_file_upload_by_id(db, file_id)
    if not fu:
        raise HTTPException(status_code=404, detail="File upload not found")
    return fu


@router.get("/files", response_model=list[schemas.FileUploadOut])
def list_file_uploads(
    user_id: str = Query(..., description="User ID"),
    session_id: Optional[str] = Query(None),
    folder: Optional[str] = Query(None, description="Filter by tags: GST, IT, ETC"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List file uploads for a user, optionally filtered by session or tags."""
    return crud.get_file_uploads_by_user(db, user_id, session_id=session_id, folder=folder, limit=limit)


@router.patch("/files/{file_id}", response_model=schemas.FileUploadOut)
def update_file_upload(file_id: int, data: schemas.FileUploadUpdate, db: Session = Depends(get_db)):
    """Update file upload (tags)."""
    fu = crud.update_file_upload(db, file_id, data)
    if not fu:
        raise HTTPException(status_code=404, detail="File upload not found")
    return fu


@router.delete("/files/{file_id}", status_code=204)
def delete_file_upload(file_id: int, db: Session = Depends(get_db)):
    """Delete a file upload record (does not delete file from storage)."""
    if not crud.delete_file_upload(db, file_id):
        raise HTTPException(status_code=404, detail="File upload not found")
    return None


# =============================================================================
# Phase 2: Subscription plans (placeholder) & Privacy info
# =============================================================================

@router.get("/subscription/plans")
def get_subscription_plans():
    """Get subscription plans (placeholder). Returns static plan definitions."""
    return {
        "plans": [
            {
                "id": "free",
                "name": "Free",
                "description": "Basic access with limited queries per day",
                "features": ["Up to 10 queries/day", "Basic support"],
                "usage_limits": {"queries_per_day": 10},
                "price": 0,
            },
            {
                "id": "pro",
                "name": "Pro",
                "description": "Extended usage for professionals",
                "features": ["Up to 100 queries/day", "Priority support", "Export history"],
                "usage_limits": {"queries_per_day": 100},
                "price": 29,
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "description": "Unlimited usage and dedicated support",
                "features": ["Unlimited queries", "Dedicated support", "SSO", "Custom integrations"],
                "usage_limits": {},
                "price": None,
            },
        ]
    }


@router.get("/privacy/info")
def get_privacy_info():
    """Get privacy information (placeholder)."""
    return {
        "privacy_policy_url": "/privacy-policy",
        "data_retention_days": 365,
        "data_usage": "Queries and responses are stored to improve service and for history. No data is shared with third parties for marketing.",
        "contact": "privacy@example.com",
    }

