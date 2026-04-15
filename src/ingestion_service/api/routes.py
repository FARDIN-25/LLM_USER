"""
Upload routes - Phase 2: folder assignment, tag extraction, document_chunks metadata.
"""
import os
import logging
import uuid
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

from src.db_service.database import get_db
from src.db_service import crud, models
from src.shared import schemas, settings
from src.shared.security import get_current_user_email
from src.ingestion_service.application.folder_service import assign_folder, extract_tags_from_content

logger = logging.getLogger("fintax")

router = APIRouter(tags=["Upload"])

# Default upload directory (from settings)
UPLOAD_DIR = settings.UPLOAD_DIR


def _ensure_upload_dir():
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


def validate_file_size(file: UploadFile, max_mb: Optional[float] = None) -> None:
    """
    Validate uploaded file size before saving. Rejects files larger than max_mb.
    Uses seek/tell on the underlying file when possible to avoid reading content.
    Raises HTTPException 413 (Payload Too Large) when file exceeds limit.
    """
    limit_mb = max_mb if max_mb is not None else getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
    try:
        if file.file.seekable():
            file.file.seek(0, 2)
            size_bytes = file.file.tell()
            file.file.seek(0)
        else:
            # Fallback: no size check if stream not seekable (e.g. chunked upload)
            logger.warning("Upload file not seekable; skipping size validation")
            return
    except Exception as e:
        logger.warning("Could not get file size for validation: %s", e)
        return

    size_mb = size_bytes / (1024 * 1024)
    if size_mb > limit_mb:
        logger.warning(
            "Upload rejected: file too large (%.2f MB > %s MB limit), filename=%s",
            size_mb, limit_mb, file.filename or "unnamed",
        )
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {limit_mb} MB.",
        )


@router.post("/upload", response_model=schemas.FileUploadOut)
def upload_file_with_folder(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    folder_assignment: Optional[str] = Form(None, description="GST, IT, or ETC"),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    db: Session = Depends(get_db),
    current_user_email: Optional[str] = Depends(get_current_user_email),
):
    """
    Upload a file with optional folder assignment and tags.
    Folder can be auto-assigned from content if not provided.
    Tags are extracted from content and merged with provided tags.
    user_id in DB is set from authenticated email (JWT); no client-supplied user_id.
    """

    if not current_user_email:
        raise HTTPException(status_code=401, detail="Authentication required. Use cookie or Authorization: Bearer token.")
    user_id = current_user_email

    # Validate file size before saving (rejects with 413 if over MAX_UPLOAD_SIZE_MB, default 10 MB)
    validate_file_size(file)

    _ensure_upload_dir()
    # Create per-user folder under UPLOAD_DIR so files are organized by user_id (email-based).
    # This keeps all uploads grouped per user while still using the same root uploads/ directory.
    safe_user_dir = "".join(ch if ch.isalnum() else "_" for ch in user_id)

    user_upload_dir = os.path.join(UPLOAD_DIR, safe_user_dir)
    Path(user_upload_dir).mkdir(parents=True, exist_ok=True)

    safe_name = file.filename or "unnamed"
    ext = Path(safe_name).suffix
    unique_name = f"{uuid.uuid4().hex[:12]}{ext}"
    # File is stored under uploads/<safe_user_dir>/<unique_name>
    file_path = os.path.join(user_upload_dir, unique_name)
    try:
        content = file.file.read()
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error("Upload write failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save file")
    finally:
        file.file.close()

    content_preview = (content[:5000].decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)[:5000])
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    if not folder_assignment:
        folder_assignment = assign_folder(
            file_path=file_path,
            file_type=ext.lstrip("."),
            content_preview=content_preview,
            tags=tag_list,
        )
    if not tag_list and content_preview:
        extracted = extract_tags_from_content(content_preview, max_tags=10)
        tag_list = extracted
    data = schemas.FileUploadCreate(
        user_id=user_id,
        session_id=session_id,
        file_path=file_path,
        file_type=ext.lstrip(".") or None,
        tags=folder_assignment,
    )
    record = crud.create_file_upload(db, data)
    return record


@router.post("/upload/metadata", response_model=schemas.FileUploadOut)
def record_upload_metadata(
    payload: dict,
    db: Session = Depends(get_db),
    current_user_email: Optional[str] = Depends(get_current_user_email),
):
    """
    Record upload metadata (e.g. when file is stored by another service).
    user_id is taken from authenticated email (JWT) only; authentication required.
    Body: file_path (required), session_id (optional), folder_assignment, file_type, tags, content_preview.
    """
    if not current_user_email:
        raise HTTPException(status_code=401, detail="Authentication required. Use cookie or Authorization: Bearer token.")
    user_id = current_user_email
    file_path = payload.get("file_path")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")
    folder_assignment = payload.get("folder_assignment")
    tags = payload.get("tags") or []
    content_preview = payload.get("content_preview")
    if not folder_assignment and content_preview:
        folder_assignment = assign_folder(content_preview=content_preview, tags=tags)
    if not tags and content_preview:
        tags = extract_tags_from_content(content_preview, max_tags=10)
    data = schemas.FileUploadCreate(
        user_id=user_id,
        session_id=payload.get("session_id"),
        file_path=file_path,
        file_type=payload.get("file_type"),
        tags=folder_assignment,
    )
    return crud.create_file_upload(db, data)


def update_document_chunk_folder_and_tags(
    db: Session,
    chunk_ids: List[int],
    folder_assignment: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> int:
    """
    Update domain and chunk_metadata (tags) on docs_chunks.
    Used by ingestion pipeline after creating chunks. Returns number of rows updated.
    """
    if not chunk_ids:
        return 0
    q = db.query(models.DocsChunk).filter(models.DocsChunk.id.in_(chunk_ids))
    count = 0
    for chunk in q.all():
        if folder_assignment is not None:
            chunk.domain = folder_assignment
        if tags is not None:
            meta = chunk.chunk_metadata or {}
            if not isinstance(meta, dict):
                meta = {}
            meta["tags"] = tags
            chunk.chunk_metadata = meta
        count += 1
    if count:
        db.commit()
    return count
