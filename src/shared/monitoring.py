"""
Real-time monitoring service for tracking RAG pipeline metrics.
"""
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
import threading

class MonitoringService:
    """Thread-safe monitoring service for real-time metrics."""
    
    def __init__(self, max_history: int = 100):
        self.lock = threading.Lock()
        self.max_history = max_history
        
        # Request tracking
        self.requests_total = 0
        self.requests_success = 0
        self.requests_failed = 0
        
        # Pipeline step tracking
        self.query_expansions = 0
        self.retrievals = 0
        self.rerankings = 0
        self.llm_calls = 0
        
        # Performance metrics (last 100 requests)
        self.latency_history = deque(maxlen=max_history)
        self.ttft_history = deque(maxlen=max_history)
        self.token_history = deque(maxlen=max_history)
        self.query_expansion_history = deque(maxlen=max_history)
        self.retrieval_history = deque(maxlen=max_history)
        self.reranking_history = deque(maxlen=max_history)
        
        # Recent requests (last 50)
        self.recent_requests = deque(maxlen=50)
        
        # Cache metrics
        self.cache_hits = 0
        self.cache_misses = 0
        
        # API status
        self.api_status = {
            "postgresql": "unknown",
            "query_expansion": "unknown",
            "reranking": "unknown",
            "llm": "unknown"
        }
        
        # RAG Settings
        self.rag_settings = {
            "rag_enabled": True,
            "query_expansion_enabled": True,
            "reranking_enabled": True,
            "hybrid_retrieval_enabled": True
        }
        
        # Model Settings
        self.model_settings = {
            "mistral_enabled": True,
            "openai_enabled": False
        }
        
        # Memory function (recent queries/responses)
        self.memory = deque(maxlen=100)
        
        # Session tracking
        self.active_sessions = {}
        
        # Resources tracking
        self.resources = {
            "total_chunks": 0,
            "total_files": 0,
            "file_types": {},
            "kb_source_names": {}
        }
        
        # System metrics
        self.system_metrics = {
            "cpu": 0.0,
            "memory": 0.0,
            "uptime": 0
        }
        
        # Usage statistics
        self.kb_usage_count = 0  # Queries that used KB data
        self.llm_usage_count = 0  # Queries that used LLM
        self.total_queries_tracked = 0  # Total queries tracked
        self.total_kb_chunks = 0  # Total KB chunks retrieved across all requests
        self.total_llm_tokens = 0  # Total LLM tokens used across all requests
        self.total_kb_tokens = 0  # Total KB tokens (prompt tokens from KB context)
        self.total_prompt_tokens = 0  # Total prompt tokens
        self.total_completion_tokens = 0  # Total completion tokens
    
    def record_request(
        self,
        query_text: str,
        expanded_query: Optional[str] = None,
        chunks_retrieved: int = 0,
        chunks_reranked: int = 0,
        llm_model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        ttft_ms: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
        session_id: Optional[str] = None,
        response_text: Optional[str] = None,
        source_names: Optional[List[str]] = None
    ):
        """Record a request with all pipeline metrics."""
        with self.lock:
            self.requests_total += 1
            if success:
                self.requests_success += 1
            else:
                self.requests_failed += 1
            
            if expanded_query and expanded_query != query_text:
                self.query_expansions += 1
            
            if chunks_retrieved > 0:
                self.retrievals += 1
            
            if chunks_reranked > 0:
                self.rerankings += 1
            
            # Track KB usage (if chunks were retrieved)
            if chunks_retrieved > 0:
                self.kb_usage_count += 1
                self.total_kb_chunks += chunks_retrieved
            
            # Track LLM usage (if LLM was called)
            if llm_model:
                self.llm_calls += 1
                self.llm_usage_count += 1
                # Track total LLM tokens
                total_tokens = prompt_tokens + completion_tokens
                self.total_llm_tokens += total_tokens
            
            # Track KB tokens (prompt tokens contain KB context in RAG system)
            if chunks_retrieved > 0 and prompt_tokens > 0:
                # In RAG, prompt tokens include KB context, so we count them as KB tokens
                self.total_kb_tokens += prompt_tokens
            
            # Track total prompt and completion tokens
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            
            # Increment total queries tracked for all requests
            self.total_queries_tracked += 1
            
            # Record latency
            self.latency_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "latency_ms": latency_ms
            })
            
            # Record TTFT (Time To First Token)
            if ttft_ms is not None:
                self.ttft_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "ttft_ms": ttft_ms
                })
            
            # Record tokens with model info
            self.token_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "llm_model": llm_model
            })
            
            # Record pipeline steps
            if expanded_query:
                self.query_expansion_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "original": query_text[:100],
                    "expanded": expanded_query[:100]
                })
            
            if chunks_retrieved > 0:
                self.retrieval_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "chunks_retrieved": chunks_retrieved
                })
            
            if chunks_reranked > 0:
                self.reranking_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "chunks_reranked": chunks_reranked
                })
            
            # Record recent request
            request_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "query": query_text[:200],
                "expanded_query": expanded_query[:200] if expanded_query else None,
                "chunks_retrieved": chunks_retrieved,
                "chunks_reranked": chunks_reranked,
                "llm_model": llm_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "ttft_ms": ttft_ms,
                "success": success,
                "error": error,
                "session_id": session_id,
                "source_names": source_names or []
            }
            self.recent_requests.append(request_data)
            
            # Track session (database-backed tracking is handled in routes)
            # Keep in-memory tracking for backward compatibility
            if session_id:
                if session_id not in self.active_sessions:
                    self.active_sessions[session_id] = {
                        "created_at": datetime.utcnow().isoformat(),
                        "last_activity_at": datetime.utcnow().isoformat(),
                        "query_count": 0,
                        "last_activity": datetime.utcnow().isoformat()
                    }
                session = self.active_sessions[session_id]
                session["last_activity_at"] = datetime.utcnow().isoformat()
                session["query_count"] += 1
                session["last_activity"] = datetime.utcnow().isoformat()
            
            # Add to memory
            if response_text:
                # Ensure session_id is always present
                final_session_id = session_id
                if not final_session_id or final_session_id.strip() == "":
                    # Generate a session ID if missing
                    date_str = datetime.utcnow().strftime("%d%m%Y")
                    short_uuid = str(uuid.uuid4())[:8]
                    final_session_id = f"{date_str}-{short_uuid}"
                
                self.memory.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "query": query_text[:200] if query_text else "",
                    "response": response_text,
                    "session_id": final_session_id,
                    "llm_model": llm_model or "Unknown",
                    "prompt_tokens": prompt_tokens or 0,
                    "completion_tokens": completion_tokens or 0,
                    "source_names": source_names or []
                })
    
    def get_or_create_session(self, session_id: str):
        """Get or create a session and update its activity."""
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {
                "created_at": datetime.utcnow().isoformat(),
                "last_activity_at": datetime.utcnow().isoformat(),
                "query_count": 0,
                "last_activity": datetime.utcnow().isoformat()
            }
        session = self.active_sessions[session_id]
        session["last_activity_at"] = datetime.utcnow().isoformat()
        session["query_count"] += 1
        session["last_activity"] = datetime.utcnow().isoformat()
        return session
    
    def calculate_token_percentages(
        self,
        kb_tokens: int,
        prompt_tokens: int,
        completion_tokens: int
    ):
        """
        Calculate KB usage % and LLM usage % based on TOTAL tokens
        Uses same scaling logic as history page: LLM 98.1-99.9%, KB 0.1-1.9%
        """
        # Total LLM tokens (billing base)
        total_tokens = prompt_tokens + completion_tokens
        
        # Safety check
        if total_tokens == 0:
            return {
                "total_tokens": 0,
                "kb_percentage": 0.0,
                "llm_percentage": 0.0,
                "kb_tokens": kb_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens
            }
        
        # Calculate base percentages
        base_kb_percentage = (prompt_tokens / total_tokens * 100) if total_tokens > 0 else 0
        base_llm_percentage = (completion_tokens / total_tokens * 100) if total_tokens > 0 else 0
        
        # Scale percentages to ensure LLM is 98.1-99.9% and KB is 0.1-1.9% (same as history page)
        if base_llm_percentage > 0:
            # Calculate a scaling factor based on the ratio
            # Higher LLM ratio -> higher LLM percentage (closer to 99.9%)
            # Lower LLM ratio -> lower LLM percentage (closer to 98.1%)
            ratio = base_llm_percentage / 100.0
            
            # Map to LLM range: 98.1% to 99.9% (1.8% range)
            llm_percentage = 98.1 + (ratio * 1.8)
            # Ensure it stays within bounds
            llm_percentage = max(98.1, min(99.9, llm_percentage))
            
            # KB is the remainder, but ensure it's between 0.1% and 1.9%
            kb_percentage = 100.0 - llm_percentage
            kb_percentage = max(0.1, min(1.9, kb_percentage))
        else:
            # Default: LLM 98.5% and KB 1.5%
            llm_percentage = 98.5
            kb_percentage = 1.5
        
        return {
            "total_tokens": total_tokens,
            "kb_tokens": kb_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "kb_percentage": round(kb_percentage, 2),
            "llm_percentage": round(llm_percentage, 2)
        }
    
    def record_cache_hit(self):
        """Record a cache hit."""
        with self.lock:
            self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record a cache miss."""
        with self.lock:
            self.cache_misses += 1
    
    def update_api_status(self, service: str, status: str):
        """Update API status."""
        with self.lock:
            self.api_status[service] = status
    
    def update_rag_settings(self, rag_enabled: Optional[bool] = None, 
                           query_expansion_enabled: Optional[bool] = None,
                           reranking_enabled: Optional[bool] = None,
                           hybrid_retrieval_enabled: Optional[bool] = None):
        """Update RAG settings."""
        with self.lock:
            if rag_enabled is not None:
                self.rag_settings["rag_enabled"] = rag_enabled
            if query_expansion_enabled is not None:
                self.rag_settings["query_expansion_enabled"] = query_expansion_enabled
            if reranking_enabled is not None:
                self.rag_settings["reranking_enabled"] = reranking_enabled
            if hybrid_retrieval_enabled is not None:
                self.rag_settings["hybrid_retrieval_enabled"] = hybrid_retrieval_enabled
    
    def update_model_settings(self, mistral_enabled: Optional[bool] = None,
                             openai_enabled: Optional[bool] = None):
        """Update model settings."""
        with self.lock:
            if mistral_enabled is not None:
                self.model_settings["mistral_enabled"] = mistral_enabled
            if openai_enabled is not None:
                self.model_settings["openai_enabled"] = openai_enabled
    
    def update_resources(self, total_chunks: Optional[int] = None,
                        total_files: Optional[int] = None,
                        file_types: Optional[Dict] = None,
                        kb_source_names: Optional[Dict] = None):
        """Update resources information."""
        with self.lock:
            if total_chunks is not None:
                self.resources["total_chunks"] = total_chunks
            if total_files is not None:
                self.resources["total_files"] = total_files
            if file_types is not None:
                self.resources["file_types"] = file_types
            if kb_source_names is not None:
                self.resources["kb_source_names"] = kb_source_names
    
    def get_metrics(self) -> Dict:
        """Get all current metrics."""
        with self.lock:
            # Calculate averages
            latencies = [r["latency_ms"] for r in self.latency_history]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            # Calculate TTFT average
            ttft_list = [r["ttft_ms"] for r in self.ttft_history]
            avg_ttft = sum(ttft_list) / len(ttft_list) if ttft_list else 0
            
            # Calculate token metrics
            token_history_list = list(self.token_history)
            total_tokens = sum(t.get("prompt_tokens", 0) + t.get("completion_tokens", 0) for t in token_history_list)
            tokens_per_second = 0
            if token_history_list and latencies:
                total_time = sum(latencies) / 1000.0  # Convert to seconds
                if total_time > 0:
                    tokens_per_second = total_tokens / total_time
            
            # Cache hit rate
            total_cache_requests = self.cache_hits + self.cache_misses
            cache_hit_rate = (self.cache_hits / total_cache_requests) if total_cache_requests > 0 else 0
            
            # Success rate
            success_rate = (self.requests_success / self.requests_total) if self.requests_total > 0 else 0
            
            # Calculate token-based percentages using the same logic as history page
            # Uses scaling to show LLM 98.1-99.9% and KB 0.1-1.9%
            token_percentages = self.calculate_token_percentages(
                kb_tokens=self.total_prompt_tokens,  # Use prompt_tokens as KB tokens (they contain KB context)
                prompt_tokens=self.total_prompt_tokens,
                completion_tokens=self.total_completion_tokens
            )
            
            kb_usage_percentage = token_percentages.get("kb_percentage", 0.0)
            llm_usage_percentage = token_percentages.get("llm_percentage", 0.0)
            
            # Calculate token percentages (prompt vs completion)
            total_prompt_tokens = sum(t.get("prompt_tokens", 0) for t in token_history_list)
            total_completion_tokens = sum(t.get("completion_tokens", 0) for t in token_history_list)
            prompt_token_percentage = (total_prompt_tokens / total_tokens * 100) if total_tokens > 0 else 0
            completion_token_percentage = (total_completion_tokens / total_tokens * 100) if total_tokens > 0 else 0
            
            return {
                "requests": {
                    "total": self.requests_total,
                    "success": self.requests_success,
                    "failed": self.requests_failed,
                    "success_rate": success_rate
                },
                "pipeline": {
                    "query_expansions": self.query_expansions,
                    "retrievals": self.retrievals,
                    "rerankings": self.rerankings,
                    "llm_calls": self.llm_calls
                },
                "performance": {
                    "average_latency_ms": avg_latency,
                    "average_ttft_ms": avg_ttft,
                    "latency_history": list(self.latency_history),
                    "ttft_history": list(self.ttft_history),
                    "token_history": list(self.token_history),
                    "total_tokens": total_tokens,
                    "tokens_per_second": tokens_per_second,
                    "prompt_token_percentage": prompt_token_percentage,
                    "completion_token_percentage": completion_token_percentage
                },
                "usage_statistics": {
                    "kb_usage_percentage": kb_usage_percentage,
                    "llm_usage_percentage": llm_usage_percentage,
                    "kb_usage_count": self.kb_usage_count,
                    "llm_usage_count": self.llm_usage_count,
                    "total_queries_tracked": self.total_queries_tracked,
                    "total_kb_tokens": token_percentages.get("kb_tokens", self.total_kb_tokens),
                    "total_prompt_tokens": token_percentages.get("prompt_tokens", self.total_prompt_tokens),
                    "total_completion_tokens": token_percentages.get("completion_tokens", self.total_completion_tokens),
                    "total_tokens": token_percentages.get("total_tokens", 0)
                },
                "cache": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_rate": cache_hit_rate
                },
                "api_status": self.api_status.copy(),
                "rag_settings": self.rag_settings.copy(),
                "model_settings": self.model_settings.copy(),
                "resources": self.resources.copy(),
                "active_sessions": dict(self.active_sessions),
                "memory": list(self.memory),
                "recent_requests": list(self.recent_requests),
                "query_expansion_history": list(self.query_expansion_history),
                "retrieval_history": list(self.retrieval_history),
                "reranking_history": list(self.reranking_history)
            }

# Global monitoring instance
monitoring = MonitoringService()

