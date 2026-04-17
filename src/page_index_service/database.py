from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.shared.config import settings


def _create_page_index_engine():
    if not settings.PAGE_INDEX_DATABASE_URL:
        return None

    return create_engine(
        settings.PAGE_INDEX_DATABASE_URL,
        pool_pre_ping=settings.DB_POOL_SIZE > 0,
        pool_size=settings.DB_POOL_SIZE if settings.DB_POOL_SIZE > 0 else None,
        max_overflow=settings.DB_MAX_OVERFLOW if settings.DB_POOL_SIZE > 0 else None,
        pool_recycle=1800,
        pool_timeout=15,
        connect_args={"connect_timeout": 10},
    )


_engine = _create_page_index_engine()

PageIndexSessionLocal: Optional[sessionmaker] = None
if _engine is not None:
    PageIndexSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine,
        expire_on_commit=False,
    )


@contextmanager
def page_index_session() -> Iterator[Session]:
    """
    Context-managed Session for the PageIndex database.

    Raises:
        RuntimeError: if PAGE_INDEX_DATABASE_URL is not configured.
    """
    if PageIndexSessionLocal is None:
        raise RuntimeError("PAGE_INDEX_DATABASE_URL is not configured")
    db: Session = PageIndexSessionLocal()
    try:
        yield db
    finally:
        db.close()

