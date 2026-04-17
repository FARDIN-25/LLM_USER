from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("fintax")


TEXT_COLUMN_CANDIDATES: Tuple[str, ...] = (
    "chunk_text",
    "content",
    "page_text",
    "extracted_text",
    "result_text",
    "output_text",
    "text",
    "body",
    "raw_text",
    "query",
    "question",
    "answer",
    "result",
    "output",
    # Keep "error" last: it's often present but not useful for retrieval.
    "error",
)

METADATA_COLUMN_CANDIDATES: Tuple[str, ...] = (
    "chunk_metadata",
    "metadata",
    "meta",
    "extra",
)


@dataclass(frozen=True)
class PageIndexConfig:
    schema: str
    table: str
    text_column: str
    has_fts_vector: bool
    metadata_column: Optional[str]


def _normalize_score(raw: float) -> float:
    # same sparse normalization used elsewhere: rank/(rank+1)
    if raw <= 0:
        return 0.0
    return raw / (raw + 1.0)


def detect_page_index_config(
    db: Session,
    *,
    schema: str = "public",
    table: str = "page_index_jobs",
) -> Optional[PageIndexConfig]:
    """
    Introspect the PageIndex table and pick the best text column.
    Supports multiple schemas without hardcoding the exact column names.
    """
    # Use a stable "fingerprint" for caching based on URL if available, otherwise per-process cache.
    bind = getattr(db, "get_bind", None)
    engine = bind() if callable(bind) else None
    url = str(getattr(engine, "url", "")) if engine is not None else ""
    fp = sha256(url.encode("utf-8")).hexdigest()[:12] if url else "no_url"

    col_map = _read_columns(db, schema, table)
    return _detect_page_index_config_cached(fp, schema, table, tuple(sorted(col_map.items())))


def _read_columns(db: Session, schema: str, table: str) -> Dict[str, str]:
    sql = text(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :table
        """
    )
    rows = db.execute(sql, {"schema": schema, "table": table}).fetchall()
    return {str(r.column_name): str(r.data_type) for r in rows} if rows else {}


@lru_cache(maxsize=32)
def _detect_page_index_config_cached(
    fp: str,
    schema: str,
    table: str,
    cols: Tuple[Tuple[str, str], ...],
) -> Optional[PageIndexConfig]:
    _ = fp
    col_map = {k: v for k, v in cols}
    if not col_map:
        return None

    text_col = None
    for c in TEXT_COLUMN_CANDIDATES:
        if c in col_map:
            text_col = c
            break

    if text_col is None:
        # fallback: pick first likely text-ish column
        for name, dtype in col_map.items():
            if dtype in ("text", "character varying", "character"):
                text_col = name
                break

    if text_col is None:
        return None

    meta_col = None
    for c in METADATA_COLUMN_CANDIDATES:
        if c in col_map:
            meta_col = c
            break

    return PageIndexConfig(
        schema=schema,
        table=table,
        text_column=text_col,
        has_fts_vector=("fts_vector" in col_map),
        metadata_column=meta_col,
    )


def page_index_search(
    db: Session,
    query: str,
    *,
    k: int = 5,
    schema: str = "public",
    table: str = "page_index_jobs",
    with_meta: bool = False,
) -> List[Dict[str, Any]]:
    """
    Retrieve PageIndex chunks from a dedicated Postgres DB.

    Returns ChatService-compatible items:
    {"text": str, "score": float, "id": str, "source": "page_index_jobs", "metadata": dict}
    """
    q = (query or "").strip()
    if not q:
        return {"results": [], "meta": {"type": "pageindex", "table": "page_index_jobs", "ids": [], "count": 0}} if with_meta else []

    cfg = detect_page_index_config(db, schema=schema, table=table)
    if cfg is None:
        return []

    full_table = f"{cfg.schema}.{cfg.table}"
    text_col = cfg.text_column

    # Tight timeout to keep UI responsive.
    db.execute(text("SET statement_timeout = '5s'"))

    if cfg.has_fts_vector:
        sql = text(
            f"""
            SELECT
                *,
                ts_rank(fts_vector, websearch_to_tsquery('english', :q)) AS raw_rank
            FROM {full_table}
            WHERE fts_vector @@ websearch_to_tsquery('english', :q)
            ORDER BY raw_rank DESC
            LIMIT :limit
            """
        )
        rows = db.execute(sql, {"q": q, "limit": max(10, k * 2)}).fetchall()
        get_raw = lambda r: float(getattr(r, "raw_rank", 0) or 0)
    else:
        # ILIKE fallback. Not as good as FTS, but works for unknown schemas.
        sql = text(
            f"""
            SELECT *
            FROM {full_table}
            WHERE CAST({text_col} AS TEXT) ILIKE :q
            LIMIT :limit
            """
        )
        rows = db.execute(sql, {"q": f"%{q}%", "limit": max(10, k * 2)}).fetchall()
        get_raw = lambda _r: 0.25  # constant weak score for fallback matches

    results: List[Dict[str, Any]] = []
    for r in rows:
        # id heuristic: prefer "id", else hash of text.
        rid = getattr(r, "id", None)
        text_value = getattr(r, text_col, None)
        txt = str(text_value or "")
        if not txt.strip():
            continue

        stable_id = str(rid) if rid is not None else sha256(txt.encode("utf-8")).hexdigest()[:16]
        score = _normalize_score(get_raw(r))

        meta: Dict[str, Any] = {"source": "page_index_jobs", "table": cfg.table, "schema": cfg.schema}
        if cfg.metadata_column:
            try:
                raw_meta = getattr(r, cfg.metadata_column, None)
                if raw_meta:
                    meta.update(dict(raw_meta))
            except Exception:
                # ignore malformed metadata
                pass

        # Full row is only needed for debug visualization (avoid bloating normal responses)
        full_row: Optional[Dict[str, Any]] = None
        if with_meta:
            try:
                # SQLAlchemy Row exposes mapping interface
                mapping = getattr(r, "_mapping", None)
                if mapping is not None:
                    full_row = {k: mapping[k] for k in mapping.keys()}
            except Exception:
                full_row = None

        payload: Dict[str, Any] = {
            "text": txt,
            "score": float(score),
            "id": f"page_index_{stable_id}",
            "source": "page_index_jobs",
            "metadata": meta,
        }
        if full_row is not None:
            payload["row"] = full_row

        results.append(payload)

    results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    top = results[:k]

    if not with_meta:
        return top

    ids: List[int] = []
    for r in top:
        rid = r.get("id")
        if isinstance(rid, str) and rid.startswith("page_index_"):
            tail = rid.replace("page_index_", "", 1)
            try:
                ids.append(int(tail))
            except Exception:
                pass

    meta = {"type": "pageindex", "table": "page_index_jobs", "ids": ids, "count": len(top)}
    return {"results": top, "meta": meta}


def page_index_search_with_meta(
    db: Session,
    query: str,
    *,
    k: int = 5,
    schema: str = "public",
    table: str = "page_index_jobs",
) -> Dict[str, Any]:
    return page_index_search(db, query, k=k, schema=schema, table=table, with_meta=True)  # type: ignore[return-value]

