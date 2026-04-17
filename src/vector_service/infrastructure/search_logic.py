from typing import List, Dict, Optional, Any, TypedDict, Union, Tuple, overload, Literal
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger("fintax")
# ---------------------------
# Type Definitions
# ---------------------------
class SearchDoc(TypedDict, total=False):
    id: Optional[Any]
    content: str
    text: str
    metadata: Dict[str, Any]

class SearchResult(TypedDict):
    doc: SearchDoc
    score: float
    type: str


# --------------------------------------------------
# --------------------------------------------------
# 🔹 Sparse Search (PostgreSQL FTS)
# --------------------------------------------------
@overload
def sparse_search_postgres(db: Session, query: str, k: int = 5, *, with_meta: Literal[False] = False) -> List[SearchResult]: ...


@overload
def sparse_search_postgres(db: Session, query: str, k: int = 5, *, with_meta: Literal[True]) -> Dict[str, Any]: ...


def sparse_search_postgres(
    db: Session, query: str, k: int = 5, *, with_meta: bool = False
) -> Union[List[SearchResult], Dict[str, Any]]:
    """
    Keyword search using websearch_to_tsquery across balance tables.
    Normalization: score = rank / (rank + 1)
    """
    if not query or query.strip() == "":
        return {"results": [], "meta": []} if with_meta else []

    logger.info(f"🔍 Sparse search (FTS) k={k}: '{query}'")
    
    # Balanced fetch: query each table for top-k then combine
    sql = text("""
        WITH docs_res AS (
            SELECT id, chunk_text, chunk_metadata, chunk_hash, domain, source_file,
                   ts_rank(fts_vector,plainto_tsquery('english', :query)) as raw_rank
            FROM docs_chunks
            WHERE fts_vector @@ plainto_tsquery('english', :query)
              AND plainto_tsquery('english', :query) IS NOT NULL
            ORDER BY raw_rank DESC
            LIMIT 50
        ),
        book_res AS (
            SELECT id, chunk_text, chunk_metadata, chunk_hash, 'Books' as domain, source_file,
                   ts_rank(fts_vector,plainto_tsquery('english', :query)) as raw_rank
            FROM book_chunks
            WHERE fts_vector @@ plainto_tsquery('english', :query)
              AND plainto_tsquery('english', :query) IS NOT NULL
            ORDER BY raw_rank DESC
            LIMIT 50
        )
        SELECT * FROM (
            SELECT id, chunk_text, chunk_metadata, chunk_hash, domain, source_file, raw_rank, 'docs' as source FROM docs_res
            UNION ALL
            SELECT id, chunk_text, chunk_metadata, chunk_hash, domain, source_file, raw_rank, 'book' as source FROM book_res
        ) combined
        ORDER BY raw_rank DESC
        LIMIT 50
    """)

    try:
        # DB-level timeout guard (Increased to 10s for stability)
        db.execute(text("SET statement_timeout = '10s'"))
        rows = db.execute(sql, {"query": query, "k": k}).fetchall()
    except Exception as e:
        logger.error(f"❌ Sparse search error (Timeout?): {e}")
        db.rollback()
        return []

    results: List[SearchResult] = []
    for r in rows:
        # Standardized Sparse Normalization: rank / (rank + 1)
        rank = float(r.raw_rank or 0)
        norm_score = rank / (rank + 1) if rank > 0 else 0
        
        results.append({
            "doc": {
                "id": f"{r.source}_{r.id}",
                "content": str(r.chunk_text or ""),
                "text": str(r.chunk_text or ""),
                "metadata": {
                    **(dict(r.chunk_metadata) if r.chunk_metadata else {}),
                    "domain": r.domain,
                    "source_file": r.source_file,
                    "chunk_hash": r.chunk_hash,
                    "source": r.source,
                    "raw_rank": float(r.raw_rank or 0),
                },
            },
            "score": norm_score,
            "type": "sparse",
        })
        
    logger.info(f"FTS Query: {query}, Results: {len(results)}")
    if not with_meta:
        return results

    ids_by_table: Dict[str, List[int]] = {"docs_chunks": [], "book_chunks": []}
    for r in results:
        doc_id = str((r.get("doc") or {}).get("id") or "")
        if "_" in doc_id:
            src, raw_id = doc_id.split("_", 1)
            try:
                rid = int(raw_id)
            except Exception:
                continue
            if src == "docs":
                ids_by_table["docs_chunks"].append(rid)
            elif src == "book":
                ids_by_table["book_chunks"].append(rid)

    meta: List[Dict[str, Any]] = [
        {"type": "fts", "table": "docs_chunks", "ids": ids_by_table["docs_chunks"], "count": len(ids_by_table["docs_chunks"])},
        {"type": "fts", "table": "book_chunks", "ids": ids_by_table["book_chunks"], "count": len(ids_by_table["book_chunks"])},
    ]
    return {"results": results, "meta": meta}


def sparse_search_postgres_with_meta(
    db: Session, query: str, k: int = 5
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper that returns both results and retrieval metadata.
    """
    return sparse_search_postgres(db, query, k, with_meta=True)  # type: ignore[return-value]


# --------------------------------------------------
# 🔹 Dense Search (pgvector)
# --------------------------------------------------
def dense_search_pgvector(db: Session, query_embedding: List[float], k: int = 5) -> List[SearchResult]:
    """
    Vector search using Cosine Distance (<=>).
    Normalization: score = 1 / (1 + distance)
    """
    logger.info(f"🔍 Dense search (Vector) k={k}")
    emb_str = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"

    sql = text("""
        WITH docs_res AS (
            SELECT id, chunk_text, chunk_metadata, chunk_hash, domain, source_file,
                   embedding <=> (:emb)::vector as distance
            FROM docs_chunks
            WHERE embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT 50
        ),
        book_res AS (
            SELECT id, chunk_text, chunk_metadata, chunk_hash, 'Books' as domain, source_file,
                   embedding <=> (:emb)::vector as distance
            FROM book_chunks
            WHERE embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT 50
        )
        SELECT * FROM (
            SELECT id, chunk_text, chunk_metadata, chunk_hash, domain, source_file, distance, 'docs' as source FROM docs_res
            UNION ALL
            SELECT id, chunk_text, chunk_metadata, chunk_hash, domain, source_file, distance, 'book' as source FROM book_res
        ) combined
        ORDER BY distance ASC
        LIMIT 50
    """)

    try:
        # DB-level timeout guard (Increased to 10s for stability)
        db.execute(text("SET statement_timeout = '10s'"))
        rows = db.execute(sql, {"emb": emb_str, "k": k}).fetchall()
    except Exception as e:
        logger.error(f"❌ Dense search error (Timeout?): {e}")
        db.rollback()
        return []

    results: List[SearchResult] = []
    for r in rows:
        # Normalization: 1 / (1 + distance)
        dist = float(r.distance or 0)
        norm_score = 1 / (1 + dist)
        
        results.append({
            "doc": {
                "id": f"{r.source}_{r.id}",
                "content": str(r.chunk_text or ""),
                "text": str(r.chunk_text or ""),
                "metadata": {
                    **(dict(r.chunk_metadata) if r.chunk_metadata else {}),
                    "domain": r.domain,
                    "source_file": r.source_file,
                    "chunk_hash": r.chunk_hash,
                    "source": r.source,
                    "raw_distance": float(r.distance or 0),
                },
            },
            "score": norm_score,
            "type": "dense",
        })
    return results


def dense_search_pgvector_with_meta(
    db: Session, query_embedding: List[float], k: int = 5
) -> Dict[str, Any]:
    results = dense_search_pgvector(db, query_embedding, k)
    ids_by_table: Dict[str, List[int]] = {"docs_chunks": [], "book_chunks": []}
    for r in results:
        doc_id = str((r.get("doc") or {}).get("id") or "")
        if "_" in doc_id:
            src, raw_id = doc_id.split("_", 1)
            try:
                rid = int(raw_id)
            except Exception:
                continue
            if src == "docs":
                ids_by_table["docs_chunks"].append(rid)
            elif src == "book":
                ids_by_table["book_chunks"].append(rid)

    meta = []
    if ids_by_table["docs_chunks"]:
        meta.append(
            {"type": "vector", "table": "docs_chunks", "ids": ids_by_table["docs_chunks"], "count": len(ids_by_table["docs_chunks"])}
        )
    if ids_by_table["book_chunks"]:
        meta.append(
            {"type": "vector", "table": "book_chunks", "ids": ids_by_table["book_chunks"], "count": len(ids_by_table["book_chunks"])}
        )
    return {"results": results, "meta": meta}

def hybrid_retrieve(
    db: Session,
    query: str,
    query_embedding: List[float],
    k: int = 5
) -> List[SearchResult]:
    """
    Hybrid search combining Dense (0.7) and Sparse (0.3).
    Deduplication via chunk_hash. Safe fallbacks and thresholding included.
    """
    logger.info(f"🚀 Starting Hybrid Retrieval: '{query}'")

    # ✅ Prevent low-context / irrelevant queries
    # Strip markdown bolding and special characters that interfere with tokenization
    import re
    # Keep alphanumeric characters, spaces, and hyphens
    clean_query = re.sub(r'[^a-zA-Z0-9\s\-]', '', query).lower().strip()

    STOP_WORDS = ["what", "is", "who", "define", "tell", "about"]

    tokens = [w for w in clean_query.split() if w not in STOP_WORDS]

    if tokens:
        search_query = " ".join(tokens)
    else:
        search_query = clean_query

    logger.info(f"🔍 FINAL SEARCH QUERY: {search_query}")
    
    dense_results = dense_search_pgvector(db, query_embedding, k * 2)
    sparse_results = sparse_search_postgres(db, search_query, k * 2)

    # Combine results
    combined_map: Dict[str, SearchResult] = {}

    # Merge Dense
    for r in dense_results:
        uid = r["doc"]["id"]
        combined_map[uid] = {
            "doc": r["doc"],
            "dense_score": r["score"],
            "sparse_score": 0.0,
            "type": "hybrid"
        }

    # Merge Sparse
    for r in sparse_results:
        uid = r["doc"]["id"]
        if uid in combined_map:
            combined_map[uid]["sparse_score"] = r["score"]
        else:
            combined_map[uid] = {
                "doc": r["doc"],
                "dense_score": 0.0,
                "sparse_score": r["score"],
                "type": "hybrid"
            }

    # Calculate final scores using Reciprocal Rank Fusion (RRF)
    # Formula: score = sum(1 / (rank + k)) where k=60
    K_RRF = 60
    
    # Sort individual lists to get ranks
    dense_results.sort(key=lambda x: x["score"], reverse=True)
    sparse_results.sort(key=lambda x: x["score"], reverse=True)

    # Map for ranks
    dense_ranks = {r["doc"]["id"]: i + 1 for i, r in enumerate(dense_results)}
    sparse_ranks = {r["doc"]["id"]: i + 1 for i, r in enumerate(sparse_results)}

    raw_list: List[SearchResult] = []
    top_score = 0.0
    
    for uid, res in combined_map.items():
        # RRF Score
        d_rank = dense_ranks.get(uid)
        s_rank = sparse_ranks.get(uid)
        
        rrf_score = 0.0
        if d_rank:
            rrf_score += 1.0 / (K_RRF + d_rank)
        if s_rank:
            rrf_score += 1.0 / (K_RRF + s_rank)
            
        # Optional: Apply weights to RRF if desired, but 1.0 is standard
        # res["score"] = (weight_dense * (1.0 / (K_RRF + d_rank) if d_rank else 0)) + \
        #                (weight_sparse * (1.0 / (K_RRF + s_rank) if s_rank else 0))
        
        res["score"] = rrf_score
        if rrf_score > top_score:
            top_score = rrf_score
        raw_list.append(res)

    # Determine dynamic threshold (RRF scores are small, typically < 0.05)
    # Adjust thresholds for RRF scale
    if top_score >= 0.03:
        threshold = 0.01
    elif top_score >= 0.015:
        threshold = 0.007   # slightly stricter
    else:
        threshold = 0.005   # much safer
    logger.info(f"RRF Dynamic Threshold set to {threshold:.6f} (Top Score: {top_score:.6f})")

    # Second pass: apply threshold
    final_list: List[SearchResult] = []
    for res in raw_list:
        if res["score"] >= threshold:
            final_list.append(res)
        else:
            logger.debug(f"Filtering out low-relevance chunk {res['doc']['id']} with score {res['score']:.4f}")

    # Content-based Deduplication using chunk_hash (SHA-256)
    seen_hashes = set()
    unique_results: List[SearchResult] = []
    
    # Sort first to keep highest scores during dedup
    final_list.sort(key=lambda x: x["score"], reverse=True)
    
    for item in final_list:
        chash = item["doc"]["metadata"].get("chunk_hash")
        if chash:
            if chash in seen_hashes:
                continue
            seen_hashes.add(chash)
        else:
            # Fallback to text hash if chunk_hash missing (safety)
            from hashlib import sha256
            txt_hash = sha256(item["doc"]["content"].encode()).hexdigest()
            if txt_hash in seen_hashes:
                continue
            seen_hashes.add(txt_hash)
            
        unique_results.append(item)

    # Final top-k
    final_top_k = unique_results[:k]

    # Structured logging for production observability
    logger.info({
        "event": "retrieval_metrics",
        "query": query,
        "dense_count": len(dense_results),
        "sparse_count": len(sparse_results),
        "unified_count": len(unique_results),
        "top_ids": [r["doc"]["id"] for r in final_top_k[:3]],
        "top_score": top_score,
        "applied_threshold": threshold
    })

    # Fallback safety
    if not final_top_k:
        logger.warning(f"⚠️ No results met the dynamic threshold {threshold:.4f} for query: {query}. Returning empty list.")
        return [{
            "doc": {"content": "NO_CONTEXT", "metadata": {}},
            "score": 0,
            "type": "none"
        }]

    return final_top_k


def hybrid_retrieve_with_meta(
    db: Session,
    query: str,
    query_embedding: List[float],
    k: int = 5,
) -> Dict[str, Any]:
    """
    Hybrid retrieval returning both results and metadata.
    """
    results = hybrid_retrieve(db=db, query=query, query_embedding=query_embedding, k=k)

    dense_pack = dense_search_pgvector_with_meta(db, query_embedding, k * 2)
    sparse_pack = sparse_search_postgres(db, query, k * 2, with_meta=True)

    meta: List[Dict[str, Any]] = []
    meta.extend(dense_pack.get("meta", []))
    meta.extend((sparse_pack or {}).get("meta", []) if isinstance(sparse_pack, dict) else [])

    return {"results": results, "meta": meta}


 

