import logging
import time
import uuid
import asyncio
import re
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.shared import schemas
from src.db_service import crud, models
from src.shared.config import settings
from src.shared.monitoring import monitoring
from src.rag_service.infrastructure.mistral import call_mistral_chat
from src.rag_service.infrastructure.prompt_templates import (
    detect_template_from_question,
    build_prompt_from_template
)
from src.followup_service.infrastructure.history_repository import HistoryRepository
from src.followup_service.application.followup_pipeline import FollowupPipeline
from src.rag_service.domain.intent_classifier import IntentClassifier
from src.vector_service.infrastructure.search_logic import hybrid_retrieve, sparse_search_postgres

logger = logging.getLogger("fintax")

# Context limits (enterprise-safe defaults)
MAX_CONTEXT_CHARS = 5000
MAX_CHUNKS_FOR_CONTEXT = 5
MAX_CHUNK_CHARS = 1000
# RRF scores are small (often ~0.01–0.03). This gate is only to block "dense-only noise".
MIN_RRF_SCORE_TO_ANSWER = 0.012


def _apply_acronym_expansions(query: str) -> str:
    """
    Expand common tax/compliance acronyms to improve sparse (FTS) recall.
    Kept intentionally small + deterministic to avoid query drift.
    """
    q = (query or "").strip()
    if not q:
        return ""
    expansions = {
        "roc": "Registrar of Companies",
        "itr": "Income Tax Return",
        "tds": "Tax Deducted at Source",
        "itc": "Input Tax Credit",
        "gstr": "Goods and Services Tax Return",
    }
    out = q
    for acr, phrase in expansions.items():
        out = re.sub(rf"\b{re.escape(acr)}\b", f"{acr.upper()} ({phrase})", out, flags=re.IGNORECASE)
    return out


def _detect_category_safe(question: str) -> str:
    """
    Detect category for the question. Uses category_service if available;
    otherwise falls back to inline keyword rules so DB never gets GENERAL by mistake.
    """
    try:
        from src.category_service.application.category_service import detect_category
        return detect_category(question)
    except Exception as e:
        logger.warning("Category service unavailable, using inline detection: %s", e)
    q = (question or "").lower()
    if "gst" in q:
        return "GST"
    if ("income tax" in q) or ("itr" in q) or ("tax rebate" in q):
        return "INCOME_TAX"
    if "tds" in q:
        return "TDS"
    if ("roc" in q) or ("company filing" in q) or ("roc annual filing" in q):
        return "ROC"
    return "GENERAL"


def _is_truncation_suspected(text: str) -> bool:
    """
    Heuristic detection for truncated LLM responses.
    Flags very short answers or those ending mid-phrase.
    """
    if not text:
        return False
    stripped = text.strip()

    # Do not treat explicit knowledge base rejections as truncations
    if "The provided knowledge base does not contain the answer" in stripped:
        return False

    if stripped.endswith("Applies") or stripped.endswith("|"):
        return True
    if len(stripped.split()) < 50:
        return True
    return False


def clean_markdown_formatting(text: str) -> str:
    """Removes basic markdown formatting for a cleaner response."""
    if not text:
        return ""
    return text.strip()



def highlight_answer_with_keywords(text: str, keywords: list) -> str:
    """Simple highlighter for keywords (can be expanded for UI)."""
    return text


def is_high_quality_content(text: str) -> bool:
    """Filters out noisy, low-quality, or meta-data heavy chunks."""
    if not text:
        return False
    text_lower = text.lower()

    return (
        len(text) > 100 and                     # avoid very short noise
        not text.isupper() and                   # avoid OCR blocks
        "form gst" not in text_lower and         # remove form-related text
        "section" not in text_lower and          # avoid raw legal clauses
        "preface" not in text_lower and          # avoid book metadata
        any(keyword in text_lower for keyword in ["gst", "tax", "bhaaskar"])
    )


def score_document(text: str) -> int:
    text_lower = text.lower()
    score = 0

    if " is " in text_lower:
        score += 5
    if "means" in text_lower:
        score += 3
    if "defined" in text_lower:
        score += 3

    return score


def normalize_query(query: str) -> str:
    query = query.lower()
    query = re.sub(r'[^a-z0-9\s]', '', query)
    return query.strip()


def extract_keywords(query: str) -> str:
    stop_words = {"what", "is", "the", "do", "you", "have", "about", "tell"}
    words = query.lower().split()
    keywords = [w for w in words if w not in stop_words]
    return " ".join(keywords)


class ChatService:
    def __init__(self, db: Session, embedding_model=None):
        self.db = db
        self.embedding_model = embedding_model
        if embedding_model is None:
            logger.warning("ChatService initialised without an embedding model — vector search will be skipped.")

    def _sanitize_question(self, question: str) -> str:
        """Removes common category prefixes that might be prepended by UI (e.g. 'GENERALwhat')."""
        if not question:
            return ""
        
        # List of prefixes to check (case-insensitive)
        prefixes = ["GENERAL", "GST", "INCOME_TAX", "TDS", "ROC", "COMPLIANCE"]
        clean_q = question.strip()
        
        for p in prefixes:
            if clean_q.upper().startswith(p):
                # Check if the prefix is immediately followed by a lowercase letter (likely a concatenation)
                # or if it's just the prefix itself + space
                prefix_len = len(p)
                if len(clean_q) > prefix_len:
                    # Case 1: Concatenated like 'GENERALwhat'
                    remainder = clean_q[prefix_len:].strip()
                    if remainder:
                        logger.info(f"🧹 Sanitized query: Removed '{p}' prefix from '{clean_q}'")
                        return remainder
        return clean_q

    def _analyze_query(self, query: str, metadata: dict) -> dict:
        q_low = query.lower()
        intent = "general"
        if any(greet in q_low for greet in ["hi", "hello", "hey", "hola", "greetings", "good morning", "good evening", "vanakkam"]):
            intent = "greeting"
        elif any(greet in q_low for greet in ["hi ", " hello", " hey"]):
             intent = "greeting"
        elif "types" in q_low or "list" in q_low:
            intent = "classification"
        elif "what is" in q_low or "define" in q_low:
            intent = "definition"
        elif "how to" in q_low or "process" in q_low:
            intent = "process"
        elif any(k in q_low for k in ["my name", "who am i", "my pan", "my tan", "my regime", "my profile", "my status", "what do you know about me", "tell me about myself"]):
            intent = "identity"
        elif "who is" in q_low or "who" in q_low:
            intent = "entity"

        entity = None
        if "bhaaskar" in q_low:
            entity = "Bhaaskar"
        
        topic = metadata.get("interaction_memory", {}).get("last_topic", "")
        gst_keywords = ["gst", "tax", "itc", "gstr", "cgst", "sgst", "igst", "return"]
        if any(kw in q_low for kw in gst_keywords):
            if "gst" in q_low or "tax" in q_low:
                topic = "Tax/GST"
            elif "itc" in q_low:
                topic = "Input Tax Credit"
            else:
                topic = "General GST"

        last_queries = metadata.get("interaction_memory", {}).get("last_queries", [])
        
        # --- CONVERSATIONAL ENTITY EXTRACTION ---
        profile_updates = {}
        
        # 1. PAN Pattern (5 letters, 4 digits, 1 letter)
        pan_match = re.search(r"([A-Z]{5}[0-9]{4}[A-Z]{1})", query.upper())
        if pan_match:
            profile_updates["pan"] = pan_match.group(1)
            
        # 2. TAN Pattern (4 letters, 5 digits, 1 letter)
        tan_match = re.search(r"([A-Z]{4}[0-9]{5}[A-Z]{1})", query.upper())
        if tan_match:
            profile_updates["tan"] = tan_match.group(1)
            
        # 3. Name Extraction (Supports "My name is X", "I am X", "Call me X", etc.)
        name_patterns = [
            r"my name is\s+([a-zA-Z\s]+)",
            r"i am\s+([a-zA-Z\s]+)",
            r"this is\s+([a-zA-Z\s]+)",
            r"call me\s+([a-zA-Z\s]+)",
            r"change my name to\s+([a-zA-Z\s]+)"
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, q_low)
            if name_match:
                name = name_match.group(1).strip().title()
                # Basic validation: ensure it's a reasonable name length
                if 2 <= len(name) <= 50 and len(name.split()) <= 4:
                    profile_updates["name"] = name
                    break

        result = {
            "interaction_memory": {
                "last_intent": intent,
                "last_entity": entity,
                "last_topic": topic,
                "last_queries": (last_queries[-4:] + [query]) if isinstance(last_queries, list) else [query]
            }
        }
        
        # Merge profile updates into the analysis result
        if profile_updates:
            result["profile"] = profile_updates
            
        return result


    async def process_chat(
        self,
        payload: schemas.QueryCreate,
        reranking_enabled: bool = True,
        reranker_type: Optional[str] = None,
        limit: int = 5,
        hybrid_retrieval_enabled: bool = True,
        query_expansion_enabled: bool = True,
        expansion_strategy: Optional[str] = None,
        use_legacy_retrieval: bool = False,
        debug: bool = True,
    ) -> Dict[str, Any]:
        start_time = time.time()
        raw_question = payload.get_question_text()
        question = self._sanitize_question(raw_question)

        if not question:
            raise HTTPException(status_code=400, detail="Missing question text")

        self._ensure_session(payload)

        if not payload.is_temporary:
            self.store_first_message(payload.session_id, question)

        chat_history_list = HistoryRepository.get_history_list(self.db, payload.session_id, limit=5)
        chat_history_text = HistoryRepository.get_history_text(self.db, payload.session_id, limit=5)

        session_obj = crud.get_chat_session_by_session_id(self.db, payload.session_id)
        session_metadata = session_obj.session_metadata if session_obj and session_obj.session_metadata else {}
        
        # --- GLOBAL METADATA HYDRATION ---
        # Ensure we always have the latest user profile (Name, PAN, etc.)
        if not session_metadata or not session_metadata.get("profile") or not session_metadata.get("profile").get("name"):
            latest_global = crud.get_latest_user_metadata(self.db, payload.user_id)
            if latest_global and latest_global.get("profile", {}).get("name"):
                # Hydrate the current session with the global profile
                crud.update_session_metadata(self.db, payload.session_id, latest_global)
                session_metadata = latest_global
        
        metadata_updates = self._analyze_query(question, session_metadata)
        
        import copy
        merged_metadata = copy.deepcopy(session_metadata)
        merged_metadata = crud.deep_merge_dict(merged_metadata, metadata_updates)


        intent = metadata_updates["interaction_memory"].get("last_intent", "general").lower()
        if intent == "general":
            intent = IntentClassifier.classify(question).lower()
        last_query = chat_history_list[-1]["content"] if chat_history_list else None

        # Use the full-fledged FollowupPipeline for detection and rewriting
        rewritten_question, is_followup = await FollowupPipeline.process(self.db, payload.session_id, question)
        if is_followup:
            logger.info(f"🔄 Follow-up detected: '{question}' -> '{rewritten_question}'")
        search_queries = [question, rewritten_question]

        payload.category = _detect_category_safe(question)

        payload.query_metadata = {
            "language": (payload.language or "english").strip() or "english",
            "category": payload.category or "GENERAL",
            "query_length": len(question or ""),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        query_row = crud.create_query(self.db, payload)
        self._track_session(payload.session_id)

        chunks: List[Dict[str, Any]] = []
        important_words: List[str] = []
        answer_data: Optional[Dict[str, Any]] = None
        viz: Optional[Dict[str, Any]] = None

        try:
            expanded_query, important_words = await self._expand_query(
                rewritten_question,
                query_expansion_enabled,
                expansion_strategy,
            )
            expanded_query = _apply_acronym_expansions(expanded_query)

            # --- HYBRID RETRIEVAL BYPASS ---
            if intent in ["greeting", "identity"]:
                logger.info(f"⚡ Personal intent detected ({intent}): Bypassing RAG retrieval.")
                chunks = []
                important_words = []
            else:
                chunks_result = await self._retrieve_documents(
                    original_query=question,
                    # IMPORTANT: Use expanded query for retrieval (previously computed but unused).
                    search_query=(expanded_query or rewritten_question),
                    limit=limit,
                    reranking_enabled=reranking_enabled,
                    hybrid_retrieval_enabled=hybrid_retrieval_enabled,
                    intent=intent,
                    use_legacy=use_legacy_retrieval,
                    debug=True,
                )
                if isinstance(chunks_result, dict):
                    chunks = chunks_result.get("chunks", [])
                    viz = chunks_result.get("viz")
                else:
                    chunks = chunks_result  # type: ignore[assignment]

            # --- DEBUG: Capture Raw Retrieval Results ---
            raw_retrieval_debug = [
                {
                    "text": c.get("text", "")[:500],
                    "score": round(float(c.get("score", 0)), 4),
                    "source": c.get("source", "Unknown")
                }
                for c in chunks[:5]
            ]
            # --------------------------------------------

            # ✅ STEP 2 — HANDLE NO_CONTEXT
            if chunks and chunks[0].get("doc", {}).get("content") == "NO_CONTEXT":
                answer_data = {
                    "answer": "No relevant information found in the knowledge base.",
                    "tags": [],
                    "language_response": {},
                    "response_metadata": {"raw_retrieval": raw_retrieval_debug}
                }
                response_row = self._save_response(
                    query_row, answer_data, chunks, start_time,
                    retrieval_method="hybrid" if hybrid_retrieval_enabled else "dense"
                )
                return {
                    "answer": answer_data["answer"],
                    "reply": answer_data["answer"],
                    "important_words": [],
                    "language_response": {},
                    "tags": [],
                    "query_id": query_row.id,
                    "response_id": response_row.id,
                    "message_id": None,
                    "session_id": payload.session_id,
                    "category": payload.category,
                    "rewritten_query": rewritten_question,
                    "raw_retrieval": raw_retrieval_debug,
                    **({"viz": viz} if viz is not None else {}),
                }

            # ✅ STEP 3 — RERANKING
            from src.rag_service.infrastructure.reranking_service import get_reranking_service

            reranker = get_reranking_service()
            chunks = reranker.rerank(
                query=rewritten_question,
                chunks=chunks[:20],   # performance limit
                top_k=limit
            )

            chunks = self._prepare_content(
                chunks,
                rewritten_question,
                limit,
                reranking_enabled,
                reranker_type,
            )

            context = self._build_context(chunks)
            context_length = len(context or "")
            
            # --- FIX TOPIC STICKINESS (IN-BETWEEN QUESTIONS) ---
            # If the best search score is very low AND the intent is not a general one, 
            # we should treat this as a context-switch and hide the old topic memory.
            top_score = chunks[0].get("score", 0) if chunks else 0
            is_unrelated = top_score < 0.015 # High threshold for relevance
            
            if intent in ["greeting", "identity"] or (is_unrelated and intent in ["entity", "definition", "process", "side_topic"]):
                context = "(No relevant tax documents found for this specific query. Respond only to the current question using the USER PROFILE data provided in the prompt.)"
                # For unrelated turns, we don't want the AI to see the old GST topic
                if intent not in ["greeting", "identity"]:
                    intent = "side_topic"

            answer_data = await self._generate_answer(
                rewritten_question,
                context,
                chunks,
                important_words,
                chat_history=chat_history_text,
                original_query=question,
                llm_category=payload.category,
                session_metadata=merged_metadata,
                intent=intent
            )

            # Enrich visualization payload with LLM + context stats
            if viz is not None and answer_data is not None:
                usage = answer_data.get("usage") or {}
                viz["context_length"] = context_length
                viz["llm"] = "mistral" if settings.MISTRAL_ENABLED else "disabled"
                viz["model"] = answer_data.get("model")
                viz["tokens"] = usage if isinstance(usage, dict) else {}
                viz["prompt_length"] = int(answer_data.get("_prompt_length") or 0)
                viz["merged_context"] = context
                viz["llm_answer"] = answer_data.get("answer", "")
                kb_chars = int(context_length or 0)
                llm_chars = len(answer_data.get("answer", "") or "")
                total_chars = kb_chars + llm_chars
                viz["kb_chars"] = kb_chars
                viz["llm_chars"] = llm_chars
                viz["kb_ratio"] = (kb_chars / total_chars) if total_chars > 0 else 0.0

            # Store debug data in metadata
            if answer_data:
                if "response_metadata" not in answer_data:
                    answer_data["response_metadata"] = {}
                answer_data["response_metadata"]["raw_retrieval"] = raw_retrieval_debug

        except Exception as e:
            logger.error(f"RAG failed: {e}", exc_info=True)
            self._record_failure(question, start_time, e, payload.session_id)
            answer_data = {
                "answer": "System temporary issue. Please try again.",
                "usage": {},
                "model": None,
                "tags": [],
                "language_response": {},
            }

        if answer_data is None:
            answer_data = {
                "answer": "System temporary issue. Please try again.",
                "usage": {},
                "model": None,
                "tags": [],
                "language_response": {},
            }

        response_row = self._save_response(
            query_row, answer_data, chunks, start_time,
            retrieval_method="hybrid" if hybrid_retrieval_enabled else "dense"
        )

        chat_message = None
        try:
            chat_message = self._create_chat_message(
                payload.session_id, query_row.id, response_row.id,
                answer_data.get("tags"), payload.user_id
            )
        except Exception as e:
            logger.warning(f"ChatMessage creation failed: {e}")

        # Save the updated rich metadata to the session
        crud.update_session_metadata(self.db, payload.session_id, metadata_updates)

        return {
            "answer": answer_data["answer"],
            "reply": answer_data["answer"],
            "important_words": important_words,
            "language_response": answer_data.get("language_response"),
            "tags": answer_data.get("tags", []),
            "query_id": query_row.id,
            "response_id": response_row.id,
            "message_id": chat_message.id if chat_message else None,
            "session_id": payload.session_id,
            "category": payload.category,
            "rewritten_query": rewritten_question,
            "is_followup": is_followup,
            **({"viz": viz} if viz is not None else {}),
        }

    def _ensure_session(self, payload: schemas.QueryCreate):
        from src.auth_service.application.session_service import (
            get_session_for_user,
            create_new_session,
            create_temporary_session,
        )
        user_id = payload.user_id
        if not user_id:
            raise HTTPException(status_code=401, detail="Missing user_id")

        if payload.is_temporary:
            if payload.session_id:
                existing = crud.get_chat_session_by_session_id(self.db, payload.session_id)
                if existing:
                    payload.session_id = existing.session_id
                    return
            temp_session = create_temporary_session(self.db, user_id)
            payload.session_id = temp_session.session_id
            return

        if payload.session_id:
            existing = get_session_for_user(self.db, payload.session_id, user_id)
            if existing:
                payload.session_id = existing.session_id
                return

        new_session = create_new_session(self.db, user_id)
        payload.session_id = new_session.session_id

    def _track_session(self, session_id: str):
        if session_id:
            try:
                from src.auth_service.application.session_service import track_session
                track_session(self.db, session_id)
            except Exception as e:
                logger.warning(f"Failed to track session: {e}")

    async def _expand_query(self, query: str, enabled: bool, strategy: Optional[str]):
        if not enabled:
            return query, []
        try:
            from src.rag_service.application.query_expansion_service import get_expansion_service, parse_strategy
            service = get_expansion_service()
            strat_enum = parse_strategy(strategy or settings.QUERY_EXPANSION_STRATEGY)
            result = await service.expand(query, strat_enum, max_tokens=200, use_important_words=True)
            expandeds = result.get("expanded_queries", [query])
            expanded = expandeds[0] if expandeds and isinstance(expandeds[0], str) else query
            words = [w for w in result.get("important_words", []) if isinstance(w, str) and w.strip()]
            return expanded, words
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return query, []

    async def _retrieve_documents(
        self,
        original_query: str,
        search_query: str,
        limit: int,
        reranking_enabled: bool,
        hybrid_retrieval_enabled: bool,
        intent: str = "GENERAL",
        use_legacy: bool = False,
        debug: bool = True,
    ) -> List[Dict]:
        """Wrapper for improved RRF retrieval with fallback to legacy logic."""
        if use_legacy:
            return await self._retrieve_documents_legacy(
                original_query, search_query, limit, reranking_enabled, hybrid_retrieval_enabled, intent
            )

        # Route the query (lookup vs semantic vs ambiguous)
        try:
            from src.retrieval.router import classify_query
            routing = classify_query(search_query)
            route = routing.get("route", "ambiguous")
            routing_confidence = routing.get("confidence", 0)
            routing_scores = {
                "lookup_score": routing.get("lookup_score", 0),
                "semantic_score": routing.get("semantic_score", 0),
            }
        except Exception as e:
            logger.warning(f"Query router failed, defaulting to ambiguous: {e}")
            route = "ambiguous"
            routing_confidence = 0
            routing_scores = {"lookup_score": 0, "semantic_score": 0}

        def _map_search_logic_results(results: List[Dict]) -> List[Dict]:
            mapped: List[Dict] = []
            for r in results:
                if r.get("doc", {}).get("content") == "NO_CONTEXT":
                    return [r]
                doc = r.get("doc", {})
                mapped.append(
                    {
                        "text": doc.get("content", ""),
                        "score": float(r.get("score") or 0),
                        "id": doc.get("id"),
                        "source": doc.get("metadata", {}).get("source", "unknown"),
                        "metadata": doc.get("metadata", {}),
                    }
                )
            return mapped

        # Use scoring-based routing to choose retrieval
        query_embedding = None
        if route in ("semantic", "ambiguous") and self.embedding_model:
            try:
                query_embedding = self.embedding_model.encode(search_query).tolist()
            except Exception as e:
                logger.error(f"Embedding generation failed for routed retrieval: {e}")

        try:
            mapped_results: List[Dict] = []
            retrieval_metas: List[Dict] = []
            kb_rows: List[Dict[str, Any]] = []
            fts_count = 0

            def _add_kb_rows(results: List[Dict], retrieval_type: str):
                """
                Convert search_logic SearchResult list to lightweight row records for UI.
                """
                for r in results[: max(0, limit * 2)]:
                    doc = (r.get("doc") or {}) if isinstance(r, dict) else {}
                    doc_id = str(doc.get("id") or "")
                    meta = (doc.get("metadata") or {}) if isinstance(doc.get("metadata"), dict) else {}
                    text_val = str(doc.get("content") or "")
                    table = None
                    row_id = None
                    if "_" in doc_id:
                        src, raw_id = doc_id.split("_", 1)
                        if src == "docs":
                            table = "docs_chunks"
                        elif src == "book":
                            table = "book_chunks"
                        row_id = raw_id
                    kb_rows.append(
                        {
                            "type": retrieval_type,
                            "table": table or "unknown",
                            "id": row_id or doc_id,
                            "score": float(r.get("score") or 0) if isinstance(r, dict) else 0.0,
                            "source_file": meta.get("source_file"),
                            "domain": meta.get("domain"),
                            "chunk_hash": meta.get("chunk_hash"),
                            "row": meta,
                            "text": text_val,
                        }
                    )

            def _add_pageindex_rows(pi_results: List[Dict[str, Any]]):
                for item in (pi_results or [])[: max(0, limit * 2)]:
                    meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                    kb_rows.append(
                        {
                            "type": "pageindex",
                            "table": "page_index_jobs",
                            "id": str(item.get("id") or ""),
                            "score": float(item.get("score") or 0),
                            "source_file": meta.get("source_file") or meta.get("source"),
                            "domain": meta.get("domain"),
                            "chunk_hash": meta.get("chunk_hash"),
                            "row": meta,
                            "text": str(item.get("text") or ""),
                        }
                    )

            def _map_pageindex_to_mapped(pi_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                mapped: List[Dict[str, Any]] = []
                for item in (pi_results or []):
                    txt = str(item.get("text") or "").strip()
                    if not txt:
                        continue
                    mapped.append(
                        {
                            "text": txt,
                            "score": float(item.get("score") or 0),
                            "id": item.get("id"),
                            "source": item.get("source", "page_index_jobs"),
                            "metadata": item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {},
                        }
                    )
                return mapped

            # Always run base retrieval signals for visualization (VECTOR + FTS)
            # These rows are for UI display, regardless of which route is ultimately used.
            try:
                from src.vector_service.infrastructure.search_logic import sparse_search_postgres_with_meta, dense_search_pgvector_with_meta

                fts_pack = sparse_search_postgres_with_meta(self.db, search_query, k=limit * 2)
                fts_results = fts_pack.get("results", [])
                fts_count = len(fts_results) if isinstance(fts_results, list) else 0
                retrieval_metas.extend(fts_pack.get("meta", []))
                _add_kb_rows(fts_results, "fts")

                if self.embedding_model:
                    try:
                        emb = self.embedding_model.encode(search_query).tolist()
                    except Exception:
                        emb = None
                    if emb:
                        vec_pack = dense_search_pgvector_with_meta(self.db, emb, k=limit * 2)
                        vec_results = vec_pack.get("results", [])
                        retrieval_metas.extend(vec_pack.get("meta", []))
                        _add_kb_rows(vec_results, "vector")
            except Exception as e:
                logger.warning(f"KB visualization retrieval failed: {e}")

            # PageIndex retrieval (3rd source) - route decides whether it participates in final answer,
            # but we always try to fetch it for debugging + optionally for final merge.
            pi_pack: Optional[Dict[str, Any]] = None
            pi_results: List[Dict[str, Any]] = []
            try:
                from src.page_index_service.database import page_index_session
                from src.page_index_service.retriever import page_index_search_with_meta
                from src.shared.config import settings

                if settings.PAGE_INDEX_DATABASE_URL:
                    with page_index_session() as pdb:
                        pi_pack = page_index_search_with_meta(pdb, search_query, k=limit * 2)
                    if isinstance(pi_pack, dict):
                        pi_results = (pi_pack.get("results") or []) if isinstance(pi_pack.get("results"), list) else []
                        retrieval_metas.append(pi_pack.get("meta", {}))
                        _add_pageindex_rows(pi_results)
            except Exception as e:
                logger.warning(f"PageIndex retrieval failed: {e}")

            if route == "lookup":
                if debug:
                    from src.vector_service.infrastructure.search_logic import sparse_search_postgres_with_meta
                    pack = sparse_search_postgres_with_meta(self.db, search_query, k=limit * 2)
                    sparse = pack.get("results", [])
                    # metas/rows already captured above; keep for safety if base retrieval failed
                    if not retrieval_metas:
                        retrieval_metas.extend(pack.get("meta", []))
                        _add_kb_rows(sparse, "fts")
                else:
                    sparse = sparse_search_postgres(self.db, search_query, k=limit * 2)
                # lookup => FTS + PageIndex (both are "lookup" sources)
                merged_lookup = _map_search_logic_results(sparse) + _map_pageindex_to_mapped(pi_results)
                # Deduplicate by id, keep max score
                by_id: Dict[str, Dict] = {}
                for item in merged_lookup:
                    iid = str(item.get("id") or "")
                    if not iid:
                        continue
                    prev = by_id.get(iid)
                    if prev is None or float(item.get("score") or 0) > float(prev.get("score") or 0):
                        by_id[iid] = item
                mapped_results = sorted(by_id.values(), key=lambda d: float(d.get("score") or 0), reverse=True)[:limit]
            elif route == "semantic":
                if not query_embedding:
                    # If embedding unavailable, degrade gracefully to FTS
                    if debug:
                        from src.vector_service.infrastructure.search_logic import sparse_search_postgres_with_meta
                        pack = sparse_search_postgres_with_meta(self.db, search_query, k=limit * 2)
                        sparse = pack.get("results", [])
                        if not retrieval_metas:
                            retrieval_metas.extend(pack.get("meta", []))
                            _add_kb_rows(sparse, "fts")
                    else:
                        sparse = sparse_search_postgres(self.db, search_query, k=limit * 2)
                    merged_sem = _map_search_logic_results(sparse) + _map_pageindex_to_mapped(pi_results)
                    by_id: Dict[str, Dict] = {}
                    for item in merged_sem:
                        iid = str(item.get("id") or "")
                        if not iid:
                            continue
                        prev = by_id.get(iid)
                        if prev is None or float(item.get("score") or 0) > float(prev.get("score") or 0):
                            by_id[iid] = item
                    mapped_results = sorted(by_id.values(), key=lambda d: float(d.get("score") or 0), reverse=True)[:limit]
                else:
                    if debug:
                        from src.vector_service.infrastructure.search_logic import hybrid_retrieve_with_meta
                        pack = hybrid_retrieve_with_meta(self.db, search_query, query_embedding, k=limit)
                        results = pack.get("results", [])
                        retrieval_metas.extend(pack.get("meta", []))
                        # Hybrid results contain merged scoring; still show them as "hybrid"
                        _add_kb_rows(results, "hybrid")
                    else:
                        results = hybrid_retrieve(
                            db=self.db,
                            query=search_query,
                            query_embedding=query_embedding,
                            k=limit,
                        )
                    mapped_hybrid = _map_search_logic_results(results)
                    merged_sem = mapped_hybrid + _map_pageindex_to_mapped(pi_results)
                    # Deduplicate by id, keep max score
                    by_id: Dict[str, Dict] = {}
                    for item in merged_sem:
                        iid = str(item.get("id") or "")
                        if not iid:
                            continue
                        prev = by_id.get(iid)
                        if prev is None or float(item.get("score") or 0) > float(prev.get("score") or 0):
                            by_id[iid] = item
                    mapped_results = sorted(by_id.values(), key=lambda d: float(d.get("score") or 0), reverse=True)[:limit]
            else:
                # ambiguous -> Hybrid + FTS + PageIndex then merge
                hybrid = []
                if query_embedding:
                    if debug:
                        from src.vector_service.infrastructure.search_logic import hybrid_retrieve_with_meta
                        pack = hybrid_retrieve_with_meta(self.db, search_query, query_embedding, k=limit)
                        hybrid = pack.get("results", [])
                        retrieval_metas.extend(pack.get("meta", []))
                        _add_kb_rows(hybrid, "hybrid")
                    else:
                        hybrid = hybrid_retrieve(
                            db=self.db,
                            query=search_query,
                            query_embedding=query_embedding,
                            k=limit,
                        )
                if debug:
                    from src.vector_service.infrastructure.search_logic import sparse_search_postgres_with_meta
                    sp = sparse_search_postgres_with_meta(self.db, search_query, k=limit * 2)
                    sparse = sp.get("results", [])
                    if not retrieval_metas:
                        retrieval_metas.extend(sp.get("meta", []))
                        _add_kb_rows(sparse, "fts")
                else:
                    sparse = sparse_search_postgres(self.db, search_query, k=limit * 2)
                mapped_hybrid = _map_search_logic_results(hybrid)
                merged = mapped_hybrid + _map_search_logic_results(sparse) + _map_pageindex_to_mapped(pi_results)

                # Deduplicate by id, keep max score
                by_id: Dict[str, Dict] = {}
                for item in merged:
                    iid = str(item.get("id") or "")
                    if not iid:
                        continue
                    prev = by_id.get(iid)
                    if prev is None or float(item.get("score") or 0) > float(prev.get("score") or 0):
                        by_id[iid] = item
                mapped_results = sorted(by_id.values(), key=lambda d: float(d.get("score") or 0), reverse=True)[:limit]

            # Grounding gate: if retrieval is weak (dense-only) and FTS is empty, force NO_CONTEXT
            # This is the main anti-hallucination guard for out-of-KB questions.
            def _no_context_viz(note: str) -> Dict[str, Any]:
                # Normalize route naming to requested UI labels
                ui_route = "hybrid" if route == "ambiguous" else route
                return {
                    "route": ui_route,
                    "confidence": int(routing_confidence or 0),
                    **routing_scores,
                    "retrievals": [m for m in retrieval_metas if isinstance(m, dict) and m.get("table")],
                    "total_chunks": 0,
                    "kb_rows": kb_rows,
                    "pageindex_rows": pi_results,
                    "notes": note,
                }

            if not mapped_results:
                return {
                    "chunks": [{"doc": {"content": "NO_CONTEXT", "metadata": {}}, "score": 0, "type": "none"}],
                    "viz": _no_context_viz("NO_CONTEXT: no results after routing/merge"),
                }

            top_score = float(mapped_results[0].get("score") or 0) if mapped_results else 0.0
            if fts_count == 0 and top_score < MIN_RRF_SCORE_TO_ANSWER:
                return {
                    "chunks": [{"doc": {"content": "NO_CONTEXT", "metadata": {}}, "score": 0, "type": "none"}],
                    "viz": _no_context_viz(
                        f"NO_CONTEXT: weak retrieval (fts_count=0, top_score={top_score:.6f} < {MIN_RRF_SCORE_TO_ANSWER})"
                    ),
                }

            # Build the visualization payload (always attached)
            total_chunks = len(mapped_results)
            # Normalize route naming to requested UI labels
            ui_route = "hybrid" if route == "ambiguous" else route

            viz_obj = {
                "route": ui_route,
                "confidence": int(routing_confidence or 0),
                **routing_scores,
                "retrievals": [m for m in retrieval_metas if isinstance(m, dict) and m.get("table")],
                "total_chunks": total_chunks,
                "kb_rows": kb_rows,
                "pageindex_rows": pi_results,
                "notes": (
                    "lookup → FTS + PageIndex"
                    if route == "lookup"
                    else ("semantic → Hybrid (vector+FTS) + PageIndex" if route == "semantic" else "hybrid → Hybrid + FTS + PageIndex")
                ),
            }

            return {"chunks": mapped_results, "viz": viz_obj}
            
        except Exception as e:
            logger.error(f"New RRF retrieval failed, falling back to legacy: {e}")
            return await self._retrieve_documents_legacy(
                original_query, search_query, limit, reranking_enabled, hybrid_retrieval_enabled, intent
            )

    async def _retrieve_documents_legacy(
        self,
        original_query: str,
        search_query: str,
        limit: int,
        reranking_enabled: bool,
        hybrid_retrieval_enabled: bool,
        intent: str = "GENERAL"
    ) -> List[Dict]:
        """
        Weighted Hybrid Retrieval: Combines FTS (Keyword) and Vector (Semantic) signals.
        - FTS Weight: 0.7
        - Vector Weight: 0.3
        """
        # 1. Normalize Query for FTS
        search_terms = []

        for q in [original_query, search_query]:
            clean_q = normalize_query(q)
            if clean_q:
                search_terms.append(clean_q)

        search_terms = list(set(search_terms))
        search_limit = limit * 2 if reranking_enabled else limit

        print(f"[QUERY DEBUG] Original: {original_query}")
        print(f"[QUERY DEBUG] Queries: {search_terms}")

        # 2. Generate Query Embedding
        query_embedding = None
        if self.embedding_model:
            try:
                query_embedding = self.embedding_model.encode(search_query).tolist()
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")

        combined_results = {}
        tables = ["docs_chunks", "book_chunks"]

        if not hybrid_retrieval_enabled:
            logger.info("Vector-only mode")

            if not query_embedding:
                return []

            combined_results = {}

            for table in tables:
                stmt_vec = text(f"""
                    SELECT id, chunk_text as content,
                           (1 / (1 + (embedding <=> CAST(:e AS vector)))) as score
                    FROM {table}
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:e AS vector)
                    LIMIT :limit
                """)

                vec_rows = self.db.execute(stmt_vec, {"e": query_embedding, "limit": limit}).fetchall()

                for r in vec_rows:
                    combined_results[f"{table}_{r.id}"] = {
                        "text": r.content,
                        "score": float(r.score or 0),
                        "id": r.id,
                        "source": table
                    }

            return sorted(combined_results.values(), key=lambda d: d["score"], reverse=True)[:limit]

        for table in tables:
            try:
                # --- FTS (0.7) ---
                for term in search_terms:
                    stmt_fts = text(f"""
                        SELECT id, chunk_text as content,
                               ts_rank(fts_vector, websearch_to_tsquery('english', :k)) as score
                        FROM {table}
                        WHERE fts_vector @@ websearch_to_tsquery('english', :k)
                        ORDER BY score DESC
                        LIMIT :limit
                    """)

                    fts_rows = self.db.execute(
                        stmt_fts,
                        {"k": term, "limit": search_limit}
                    ).fetchall()

                    for r in fts_rows:
                        doc_id = f"{table}_{r.id}"
                        combined_results[doc_id] = {
                            "text": r.content,
                            "score": float(r.score or 0) * 0.7,
                            "id": r.id,
                            "source": table
                        }

                # --- VECTOR (0.3) ---
                if query_embedding:
                    stmt_vec = text(f"""
                        SELECT id, chunk_text as content,
                               (1 / (1 + (embedding <=> CAST(:e AS vector)))) as score
                        FROM {table}
                        WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> CAST(:e AS vector)
                        LIMIT :limit
                    """)

                    vec_rows = self.db.execute(
                        stmt_vec,
                        {"e": query_embedding, "limit": search_limit}
                    ).fetchall()

                    for r in vec_rows:
                        doc_id = f"{table}_{r.id}"
                        v_score = float(r.score or 0) * 0.3

                        if doc_id in combined_results:
                            combined_results[doc_id]["score"] += v_score
                        else:
                            combined_results[doc_id] = {
                                "text": r.content,
                                "score": v_score,
                                "id": r.id,
                                "source": table
                            }

            except Exception as e:
                logger.error(f"Hybrid search failed for {table}: {e}")
                self.db.rollback()

        # 4. Fallback if result-less
        final_chunks = list(combined_results.values())
        if not final_chunks:
            logger.info("Hybrid search yielded 0 results, attempting FTS fallback...")

        print(f"[RETRIEVAL DEBUG] Candidates: {len(final_chunks)}")

        # 5. Filter and Rank
        filtered_docs = sorted(
            final_chunks,
            key=lambda d: d.get("score", 0),
            reverse=True
        )

        filtered_docs = filtered_docs[:limit * 3]

        return filtered_docs


    def _prepare_content(self, chunks: List[Dict], query: str, limit: int, reranking_enabled: bool, reranker_type: Optional[str]) -> List[Dict]:
        return chunks[:limit]

    def _build_context(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "No specific context available."
        context_parts = []
        for idx, c in enumerate(chunks[:MAX_CHUNKS_FOR_CONTEXT]):
            text_val = (c.get("text") or "").strip()
            if not text_val:
                continue
            if len(text_val) > MAX_CHUNK_CHARS:
                text_val = text_val[:MAX_CHUNK_CHARS]
            context_parts.append(f"[Source: {c.get('source', 'unknown')}]\n{text_val}\n\n")
        return "".join(context_parts)

    async def _generate_answer(
        self,
        query: str,
        context: str,
        chunks,
        important_words,
        chat_history="",
        original_query="",
        llm_category="GENERAL",
        session_metadata=None,
        intent="general"
    ) -> Dict[str, Any]:
        if intent in ["greeting", "identity"]:
            # For identity/greetings, we use the simpler "greeting" template
            # and explicitly clear most tax-heavy params to avoid confusion.
            template_id = "greeting"
            params = {}
            if intent == "greeting":
                # Clear history for greeting turns to break the GST/Tax stickiness
                chat_history = "Greeting: This is a fresh start."
            elif intent == "identity":
                # For identity updates, we clear history so it doesn't repeat old tax procedures
                chat_history = "Identity Confirmation: Updating user profile records."
            else:
                # For identity questions, we want to keep history but prioritize profile
                pass
        else:
            template_id, params = detect_template_from_question(query)

        # Build user profile string
        profile_str = ""
        if session_metadata:
            p = session_metadata.get("profile", {})
            f = session_metadata.get("financials", {})
            n = session_metadata.get("notices", {})
            lines = []
            if p.get("name"): lines.append(f"- Name: {p.get('name')}")
            if f.get("tax_regime"): lines.append(f"- Tax Regime: {f.get('tax_regime')}")
            if f.get("income_sources"): lines.append(f"- Income Sources: {', '.join(f.get('income_sources'))}")
            if n.get("active_notices"): lines.append(f"- Active Notices: {len(n.get('active_notices'))} pending")
            profile_str = "\n".join(lines)

        params.update({
            "retrieved_context": context,
            "user_query": query,
            "chat_history": chat_history,
            "user_profile": profile_str,
            "original_query": original_query,
            "rewritten_query": query,
            "intent": intent,
            "metadata": session_metadata or {}
        })
        
        prompt = build_prompt_from_template(template_id, params)
        answer = ""
        llm_model = settings.MISTRAL_MODEL
        if settings.MISTRAL_ENABLED:
            try:
                from src.rag_service.infrastructure.mistral import async_call_mistral_chat
                response = await async_call_mistral_chat(prompt, settings.MISTRAL_API_KEY, llm_model)
                answer = clean_markdown_formatting(response.get("content", ""))
                usage = response.get("usage") or {}
                llm_model = response.get("model") or llm_model
            except Exception as e:
                logger.error(f"LLM failed: {e}")
                answer = f"Fallback context:\n{context[:500]}"
                usage = {}
        else:
            answer = f"Fallback context:\n{context[:500]}"
            usage = {}

        # Never return an empty answer (frontend shows ". no answer provided ...")
        if not (answer or "").strip():
            answer = "System temporary issue. Please try again."

        # FIX: Always return tags and language_response so callers never get KeyError
        return {
            "answer": answer,
            "usage": usage if isinstance(usage, dict) else {},
            "model": llm_model,
            "tags": [],
            "language_response": {},
            "_prompt_length": len(prompt),
        }

    def _save_response(self, query_row, answer_data, chunks, start_time, retrieval_method="dense"):
        retrieved_context_ids = [str(c.get("id")) for c in chunks if c.get("id")]
        metadata = answer_data.get("response_metadata", {})
        metadata["retrieval_method"] = retrieval_method
        
        response_create = schemas.ResponseCreate(
            query_id=query_row.id,
            response_text=answer_data.get("answer", ""),
            retrieved_context_ids=retrieved_context_ids,
            llm_model=answer_data.get("model"),
            latency_ms=int((time.time() - start_time) * 1000),
            prompt_tokens=0, completion_tokens=0, total_tokens=0,
            tags=answer_data.get("tags", []),
            language_response=answer_data.get("language_response", {}),
            response_metadata=metadata,
        )
        return crud.create_response(self.db, response_create)

    def _create_chat_message(self, session_id, query_id, response_id, tags, user_id=None):
        if not user_id:
            return None
        return crud.create_chat_message(
            self.db,
            schemas.ChatMessageCreate(
                session_id=session_id,
                query_id=query_id,
                response_id=response_id,
                tags=tags
            )
        )

    def _record_failure(self, query, start_time, error, session_id):
        monitoring.record_request(
            query_text=query,
            latency_ms=int((time.time() - start_time) * 1000),
            success=False,
            error=str(error),
            session_id=session_id
        )

    async def regenerate_response(self, query_id: int, **kwargs) -> Dict[str, Any]:
        query_row = crud.get_query_by_id(self.db, query_id)
        response_row = crud.get_response_by_query_id(self.db, query_id)
        if not query_row or not response_row:
            raise HTTPException(status_code=404)
        retrieved = await self._retrieve_documents(
            query_row.query_text, query_row.query_text, 5, True, True
        )

        viz = None
        chunks = []
        if isinstance(retrieved, dict):
            viz = retrieved.get("viz")
            chunks = retrieved.get("chunks", []) or []
        else:
            chunks = retrieved or []

        context = self._build_context(chunks)
        answer_data = await self._generate_answer(query_row.query_text, context, chunks, [])
        crud.update_response_content(
            self.db,
            response_id=response_row.id,
            response_text=answer_data["answer"],
            retrieved_context_ids=[c.get("id") for c in chunks if c.get("id")]
        )
        # FIX: include response_id so /chat/regenerate route doesn't get a KeyError
        return {
            "answer": answer_data["answer"],
            "query_id": query_id,
            "response_id": response_row.id,
            **({"viz": viz} if viz is not None else {}),
        }

    # =============================================================================
    # Session & History Service Methods
    # =============================================================================

    def ensure_session_exists(self, user_id: str):
        from src.auth_service.application.session_service import ensure_session_exists as _ensure
        return _ensure(self.db, user_id)

    def store_first_message(self, session_id: str, question: str) -> None:
        if not session_id or not (question or "").strip():
            return
        session = crud.get_chat_session_by_session_id(self.db, session_id)
        if not session:
            return
        existing = (session.history or {}) if isinstance(session.history, dict) else {}
        if existing.get("title"):
            return
        title = self.generate_chat_title(question)
        crud.update_chat_session_history(
            self.db, session_id,
            {"title": title or "New chat", "first_question": (question or "").strip()[:1000]}
        )

    def get_user_history(self, user_id: str, limit: int = 100):
        sessions = crud.get_chat_sessions_by_user(self.db, user_id, limit=limit)
        calculate_session_badge = None
        try:
            from src.chat_service.application.session_badge_service import calculate_session_badge
        except Exception as e:
            logger.warning(f"session_badge_service unavailable: {e}")

        out = []
        for s in sessions:
            hist = (s.history or {}) if isinstance(s.history, dict) else {}
            title = hist.get("title")
            if not title:
                continue
            category = calculate_session_badge(self.db, s.session_id) if calculate_session_badge else "GENERAL"
            out.append({
                "session_id": s.session_id,
                "title": title,
                "category": category,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None
            })
        return out

    def get_session_messages(self, session_id: str, limit: int = 500):
        return crud.get_session_messages_joined(self.db, session_id, limit=limit, exclude_hidden=True)

    def update_session_title(self, session_id: str, title: str, user_id: str):
        session = crud.get_chat_session_by_session_id(self.db, session_id)
        if not session or session.user_id != user_id:
            return False
        existing = (session.history or {}) if isinstance(session.history, dict) else {}
        updated = {**existing, "title": (title or "").strip()[:200] or "New chat"}
        crud.update_chat_session_history(self.db, session_id, updated)
        return True

    def delete_session(self, session_id: str, user_id: str):
        session = crud.get_chat_session_by_session_id(self.db, session_id)
        if not session:
            return "not_found"
        if session.user_id.strip() != user_id.strip():
            return "not_owned"
        return crud.delete_chat_session(self.db, session_id)

    def generate_chat_title(self, first_question: str) -> Optional[str]:
        if not first_question:
            return "New chat"
        prompt = f"Generate a short 4-word title for this chat: {first_question[:500]}"
        try:
            if not settings.MISTRAL_ENABLED:
                return " ".join(first_question.split()[:4])
            response = call_mistral_chat(prompt, settings.MISTRAL_API_KEY, settings.MISTRAL_MODEL)
            return response.get("content", "New chat").strip()[:100]
        except Exception as e:
            logger.warning(f"generate_chat_title failed: {e}")
            return "New chat"

    def set_message_reaction(self, message_id: int, user_id: str, emoji: str):
        return crud.set_message_reaction(self.db, message_id, user_id, emoji)

    def get_message_reaction(self, message_id: int) -> str:
        return crud.get_message_reaction(self.db, message_id)


def get_chat_service(db: Session, embedding_model=None):
    return ChatService(db, embedding_model)