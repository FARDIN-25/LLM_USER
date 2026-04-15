"""
Chat and Query routes - RAG pipeline endpoints.
"""
import os
import time
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from app.database import get_db
from app import schemas, crud
from app.vector_search import semantic_search
from app.services.llm_service import create_prompt
from app.services.openrouter import call_openrouter_chat

logger = logging.getLogger("fintax")

router = APIRouter(tags=["Chat"])

# Initialize embedding model (shared across requests)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def rerank_chunks(query: str, chunks: list, top_k: int = 5) -> list:
    """Rerank chunks using cross-encoder if available."""
    try:
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device='cpu')
        
        pairs = [[query, chunk.get("text", chunk.get("content", ""))] for chunk in chunks]
        scores = reranker.predict(pairs)
        
        # Combine chunks with scores
        scored_chunks = list(zip(chunks, scores))
        # Sort by score (descending)
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        # Return top_k chunks
        return [chunk for chunk, _ in scored_chunks[:top_k]]
    except Exception as e:
        logger.warning(f"Reranking not available: {e}")
        return chunks[:top_k]


@router.post("/chat")
async def chat(
    payload: dict,
    db: Session = Depends(get_db),
    reranking_enabled: bool = Query(True),
    limit: int = Query(5)
):
    """
    Chat endpoint - KB + LLM = Answer (RAG Pipeline)
    
    Request body:
    {
        "question": "What is GST?"
    }
    """
    try:
        question = payload.get("question") or payload.get("query_text")
        if not question:
            raise HTTPException(status_code=400, detail="Missing 'question' field")
        
        logger.info(f"📨 Chat request: {question[:100]}")
        
        # Use query endpoint logic
        # Preserve optional language hint from payload (e.g. 'english' or 'tamil')
        query_create = schemas.QueryCreate(query_text=question, language=payload.get("language"))
        result = await query_rag(
            payload=query_create,
            db=db,
            query_expansion_enabled=False,  # Query expansion optional
            reranking_enabled=reranking_enabled,
            limit=limit
        )
        
        return {
            "status": "success",
            "answer": result["answer"],
            "kb_contribution": result.get("kb_contribution"),
            "llm_contribution": result.get("llm_contribution"),
            "chunks": result.get("chunks"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_rag(
    payload: schemas.QueryCreate,
    db: Session = Depends(get_db),
    query_expansion_enabled: bool = Query(False),
    reranking_enabled: bool = Query(True),
    limit: int = Query(5)
):
    """
    Full RAG pipeline:
    1. Embedding
    2. Semantic search (pgvector)
    3. Reranking (optional)
    4. LLM generation
    """
    start_time = time.time()
    
    question = payload.get_question_text()
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question' or 'query_text' field")
    
    # 1️⃣ Save query
    query_row = crud.create_query(db, payload)
    
    # 2️⃣ Query expansion (optional - requires query_expansion module)
    expanded_query = question
    if query_expansion_enabled:
        try:
            from app.query_expansion.tax_vocabulary import expand_query
            expanded_query = expand_query(question)
            logger.info(f"Query expanded: {question} -> {expanded_query}")
        except ImportError:
            logger.warning("Query expansion module not available")
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
    
    # 3️⃣ Embed question
    query_embedding = await asyncio.to_thread(
        embedding_model.encode, expanded_query
    )
    query_embedding = query_embedding.tolist()
    
    # 4️⃣ Retrieval
    search_limit = limit * 2 if reranking_enabled else limit
    logger.info(f"🔍 Searching with limit={search_limit}, reranking={reranking_enabled}")
    
    try:
        chunks = semantic_search(db, query_embedding, top_k=search_limit)
    except Exception as e:
        logger.error(f"❌ Semantic search failed: {e}", exc_info=True)
        db.rollback()
        chunks = []
    
    # 5️⃣ Reranking (optional)
    if reranking_enabled and chunks:
        try:
            logger.info(f"🔄 Reranking {len(chunks)} chunks")
            chunks = rerank_chunks(question, chunks, top_k=limit)
            logger.info(f"✅ Reranked to {len(chunks)} chunks")
        except Exception as e:
            logger.warning(f"⚠️ Reranking failed: {e}. Using original order.")
            chunks = chunks[:limit]
    else:
        chunks = chunks[:limit]
    
    logger.info(f"📚 Retrieved {len(chunks)} chunks for context")
    
    # 6️⃣ Build context
    MAX_CONTEXT_CHARS = 6000
    context_parts = []
    current_len = 0

    for c in chunks:
        chunk_text = c.get('text', c.get('content', ''))
        source = c.get('metadata', {}).get('source', 'unknown')
        block = f"[Source: {source}]\n{chunk_text}\n\n"

        if current_len + len(block) > MAX_CONTEXT_CHARS:
            break

        context_parts.append(block)
        current_len += len(block)

    context = "".join(context_parts)
    
    # 7️⃣ Create prompt
    logger.info(f"📝 Creating prompt (context length: {len(context)} chars)")
    # Pass preferred language from the incoming payload (if provided)
    preferred_lang = getattr(payload, "language", None)
    prompt = create_prompt(context, question, preferred_language=preferred_lang)
    
    # 8️⃣ Call LLM
    logger.info(f"🤖 Calling LLM...")
    answer = ""
    llm_model = None
    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct")
        
        if api_key:
            logger.info(f"🔑 Using LLM model: {model}")
            try:
                result = call_openrouter_chat(prompt, api_key, model)
                answer = result.get("content", "")
                llm_model = result.get("model", model)
                logger.info(f"✅ LLM response received ({len(answer)} chars)")
            except HTTPException as http_err:
                logger.error(f"❌ LLM HTTP error: {http_err.detail}")
                raise http_err
        else:
            answer = f"Based on documents:\n{context[:2000]}"
            logger.warning("⚠️ OPENROUTER_API_KEY not set. Using fallback answer.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ LLM call failed: {e}", exc_info=True)
        answer = f"Based on documents:\n{context[:2000]}"
    
    # 9️⃣ Save response
    latency_ms = int((time.time() - start_time) * 1000)
    response_create = schemas.ResponseCreate(
        query_id=query_row.id,
        response_text=answer,
        retrieved_context_ids=[c.get("id") for c in chunks if c.get("id")],
        llm_model=llm_model,
        latency_ms=latency_ms
    )
    crud.create_response(db, response_create)
    # Compute contribution details for this response (backend-driven heuristic)
    CHAR_PER_TOKEN = 4.0
    chunks_count = len(chunks)
    kb_context_chars = sum(len(c.get("text", c.get("content", "")) or "") for c in chunks)
    sources = []
    for c in chunks:
        src = (c.get("metadata") or {}).get("source") or (c.get("metadata") or {}).get("file_path")
        if src:
            sources.append(src)
    # Deduplicate sources
    seen = set()
    dedup_sources = []
    for s in sources:
        if s not in seen:
            seen.add(s)
            dedup_sources.append(s)

    response_chars = len(answer or "")
    total_tokens = int(response_chars / CHAR_PER_TOKEN) if response_chars > 0 else 0

    if chunks_count <= 0:
        kb_pct = 0.0
        llm_pct = 100.0
    else:
        llm_equiv = (response_chars / CHAR_PER_TOKEN) if response_chars > 0 else 0.0
        kb_weight = float(chunks_count)
        llm_weight = float(llm_equiv)
        total_weight = kb_weight + llm_weight if (kb_weight + llm_weight) > 0 else 1.0
        kb_pct = max(0.0, min(100.0, (kb_weight / total_weight) * 100.0))
        llm_pct = max(0.0, min(100.0, 100.0 - kb_pct))

    kb_contribution = {
        "percentage": round(kb_pct, 1),
        "chunks_count": chunks_count,
        "context_chars": kb_context_chars,
        "sources": dedup_sources,
    }

    llm_contribution = {
        "percentage": round(llm_pct, 1),
        "response_chars": response_chars,
        "total_tokens": total_tokens,
        "model": llm_model,
    }

    return {
        "question": question,
        "answer": answer,
        "chunks": [
            {
                "id": c.get("id"),
                "content": c.get("text", c.get("content", "")),
                "metadata": c.get("metadata", {})
            }
            for c in chunks
        ],
        "query_expansion_enabled": query_expansion_enabled,
        "reranking_enabled": reranking_enabled,
        "latency_ms": latency_ms,
        "kb_contribution": kb_contribution,
        "llm_contribution": llm_contribution,
    }

