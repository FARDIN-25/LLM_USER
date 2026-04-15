"""
Comprehensive Reranking Service
Supports multiple reranking methods:
1. Cross-encoder rerankers (sentence-transformers)
2. Cohere reranker
3. BGE reranker
4. LLM-based reranking

Enhanced Features:
- Re-score top 30 → select best 5
- Penalize generic chunks
- Boost exact matches
- Boost section matches
"""
import os
import re
import logging
from typing import List, Dict, Optional, Literal, Tuple
from enum import Enum
from src.shared.config import settings

logger = logging.getLogger("fintax")


class RerankerType(str, Enum):
    """Supported reranker types."""
    CROSS_ENCODER = "cross-encoder"
    COHERE = "cohere"
    BGE = "bge"
    LLM = "llm"


class RerankingService:
    """Unified reranking service supporting multiple reranker backends."""
    
    def __init__(self):
        self._cross_encoder_rerankers = {}
        self._cohere_reranker = None
        self._bge_reranker = None
        self._llm_reranker_available = False
        self._available_types = set()
        
        # Initialize all available rerankers
        self._initialize_rerankers()
    
    def _initialize_rerankers(self):
        """Initialize all available reranker types."""
        # 1. Cross-encoder rerankers
        self._init_cross_encoder()
        
        # 2. Cohere reranker
        self._init_cohere()
        
        # 3. BGE reranker
        self._init_bge()
        
        # 4. LLM-based reranker
        self._init_llm()
        
        logger.info(f"✅ Reranking service initialized. Available types: {self._available_types}")
    
    def _init_cross_encoder(self):
        """Initialize cross-encoder rerankers."""
        try:
            from sentence_transformers import CrossEncoder
            
            # Try multiple cross-encoder models
            models = [
                'cross-encoder/ms-marco-MiniLM-L-6-v2',  # Default lightweight
                'cross-encoder/ms-marco-MiniLM-L-12-v2',  # Better accuracy
                'cross-encoder/ms-marco-electra-base',  # Even better
            ]
            
            for model_name in models:
                try:
                    reranker = CrossEncoder(model_name, device='cpu')
                    self._cross_encoder_rerankers[model_name] = reranker
                    self._available_types.add(RerankerType.CROSS_ENCODER)
                    logger.info(f"✅ Cross-encoder reranker loaded: {model_name}")
                    # Use first successful model as default
                    if 'default' not in self._cross_encoder_rerankers:
                        self._cross_encoder_rerankers['default'] = reranker

                    break
                except Exception as e:
                    logger.debug(f"Failed to load {model_name}: {e}")
                    continue
            
            # Set default if not set
            if self._cross_encoder_rerankers and 'default' not in self._cross_encoder_rerankers:
                self._cross_encoder_rerankers['default'] = list(self._cross_encoder_rerankers.values())[0]
                
        except ImportError:
            logger.warning("⚠️ sentence-transformers not available for cross-encoder reranking")
        except Exception as e:
            logger.error(f"❌ Cross-encoder initialization failed: {e}", exc_info=True)
    
    def _init_cohere(self):
        """Initialize Cohere reranker."""
        try:
            import cohere
            
            cohere_api_key = settings.COHERE_API_KEY
            if not cohere_api_key:
                logger.debug("COHERE_API_KEY not set. Cohere reranker unavailable (optional).")
                return
            
            self._cohere_client = cohere.Client(api_key=cohere_api_key)
            self._available_types.add(RerankerType.COHERE)
            logger.info("✅ Cohere reranker initialized")
            
        except ImportError:
            logger.debug("cohere package not installed. Cohere reranker unavailable (optional). Install with: pip install cohere")
        except Exception as e:
            logger.error(f"❌ Cohere reranker initialization failed: {e}", exc_info=True)
    
    def _init_bge(self):
        """Initialize BGE reranker."""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch
            
            # Try to load BGE reranker model
            model_name = "BAAI/bge-reranker-base"  # or "BAAI/bge-reranker-large"
            
            try:
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForSequenceClassification.from_pretrained(model_name)
                model.to(device)
                model.eval()
                
                self._bge_tokenizer = tokenizer
                self._bge_model = model
                self._bge_device = device
                self._available_types.add(RerankerType.BGE)
                logger.info(f"✅ BGE reranker initialized: {model_name} on {device}")
            except Exception as e:
                logger.debug(f"Failed to load BGE model {model_name}: {e} (optional)")
                
        except ImportError:
            logger.debug("transformers package not available for BGE reranker (optional)")
        except Exception as e:
            logger.error(f"❌ BGE reranker initialization failed: {e}", exc_info=True)
    
    def _init_llm(self):
        """Initialize LLM-based reranking."""
        try:
            # Check if MISTRAL API is available (for LLM-based reranking)
            mistral_key = settings.MISTRAL_API_KEY
            if mistral_key:
                self._llm_reranker_available = True
                self._available_types.add(RerankerType.LLM)
                logger.info("✅ LLM-based reranking available (using MISTRAL)")
            else:
                logger.warning("⚠️ MISTRAL_API_KEY not set. LLM-based reranking unavailable.")
        except Exception as e:
            logger.error(f"❌ LLM reranker initialization failed: {e}", exc_info=True)
    
    def is_available(self, reranker_type: Optional[RerankerType] = None) -> bool:
        """Check if a specific reranker type is available."""
        if reranker_type is None:
            return len(self._available_types) > 0
        return reranker_type in self._available_types
    
    def get_available_types(self) -> List[str]:
        """Get list of available reranker types."""
        return [t.value for t in self._available_types]
    
    def rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_k: int = 5,
        reranker_type: Optional[RerankerType] = None,
        initial_limit: int = 30
    ) -> List[Dict]:
        """
        Rerank chunks using the specified reranker type with advanced scoring.
        
        Process:
        1. Get initial reranker scores for top 30 chunks
        2. Apply advanced scoring (boost exact matches, section matches; penalize generic)
        3. Select best 5 chunks
        
        Args:
            query: The search query
            chunks: List of chunk dictionaries with 'text' or 'content' keys
            top_k: Number of top chunks to return (default: 5)
            reranker_type: Type of reranker to use. If None, uses first available.
            initial_limit: Number of chunks to re-score initially (default: 30)
        
        Returns:
            List of reranked chunks
        """
        if not chunks:
            return []

        #every uery will be in lower case
        query = query.lower().strip()
        
        # Limit chunks for initial reranking (top 30)
        chunks_to_rerank = chunks[:min(initial_limit, len(chunks))]
        
        # Determine which reranker to use
        if reranker_type is None:
            # Use first available reranker in priority order
            if RerankerType.CROSS_ENCODER in self._available_types:
                reranker_type = RerankerType.CROSS_ENCODER
            elif RerankerType.COHERE in self._available_types:
                reranker_type = RerankerType.COHERE
            elif RerankerType.BGE in self._available_types:
                reranker_type = RerankerType.BGE
            elif RerankerType.LLM in self._available_types:
                reranker_type = RerankerType.LLM
            else:
                logger.warning("⚠️ No rerankers available. Using basic scoring.")
                return self._apply_advanced_scoring(query, chunks, top_k)
        
        # Route to appropriate reranker
        try:
            if reranker_type == RerankerType.CROSS_ENCODER:
                reranked = self._rerank_cross_encoder(query, chunks_to_rerank, initial_limit)
            elif reranker_type == RerankerType.COHERE:
                reranked = self._rerank_cohere(query, chunks_to_rerank, initial_limit)
            elif reranker_type == RerankerType.BGE:
                reranked = self._rerank_bge(query, chunks_to_rerank, initial_limit)
            elif reranker_type == RerankerType.LLM:
                reranked = self._rerank_llm(query, chunks_to_rerank, initial_limit)
            else:
                logger.warning(f"⚠️ Unknown reranker type: {reranker_type}. Using basic scoring.")
                return self._apply_advanced_scoring(query, chunks, top_k)
            
            # Apply advanced scoring and select best 5
            return reranked[:top_k]
        except Exception as e:
            logger.error(f"❌ Reranking failed with {reranker_type}: {e}", exc_info=True)
            return self._apply_advanced_scoring(query, chunks, top_k)
    
    def _rerank_cross_encoder(self, query: str, chunks: List[Dict], top_k: int) -> List[Dict]:
        """Rerank using cross-encoder."""
        if not self._cross_encoder_rerankers:
            return chunks[:top_k]
        
        reranker = self._cross_encoder_rerankers.get('default') or list(self._cross_encoder_rerankers.values())[0]
        
        # Prepare pairs
        pairs = []
        for chunk in chunks:
            chunk_text = chunk.get("text", chunk.get("content", ""))
            pairs.append([query, chunk_text])
        
        # Get scores
        scores = reranker.predict(pairs)
        
        # Normalize scores to [0, 1] range if needed
        if len(scores) > 0:
            min_score = min(scores)
            max_score = max(scores)
            if max_score > min_score:
                scores = [(s - min_score) / (max_score - min_score) for s in scores]
            else:
                scores = [0.5] * len(scores)
        
        # Combine chunks with scores
        scored_chunks = []
        for chunk, score in zip(chunks, scores):
            chunk_with_score = chunk.copy()
            chunk_with_score["score"] = float(score)
            scored_chunks.append(chunk_with_score)
        
        # Sort by score (descending)
        scored_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return scored_chunks[:top_k]
    
    def _rerank_cohere(self, query: str, chunks: List[Dict], top_k: int) -> List[Dict]:
        """Rerank using Cohere API."""
        if not hasattr(self, '_cohere_client'):
            return chunks[:top_k]
        
        # Prepare documents
        documents = []
        for chunk in chunks:
            chunk_text = chunk.get("text", chunk.get("content", ""))
            documents.append(chunk_text)
        
        # Call Cohere rerank API
        try:
            results = self._cohere_client.rerank(
                model='rerank-english-v3.0',  # or 'rerank-multilingual-v3.0'
                query=query,
                documents=documents,
                top_n=top_k
            )
            
            # Map results back to chunks with scores
            reranked_chunks = []
            # Cohere returns results in order of relevance
            # Handle both response formats (results.results or direct list)
            if hasattr(results, 'results'):
                result_list = results.results
            else:
                result_list = results
            
            for result in result_list:
                # Get index and relevance score from result object
                index = getattr(result, 'index', None)
                if index is None:
                    # Try to get from dictionary if it's a dict
                    index = result.get('index') if isinstance(result, dict) else None
                
                relevance_score = getattr(result, 'relevance_score', None)
                if relevance_score is None:
                    relevance_score = result.get('relevance_score', 0.5) if isinstance(result, dict) else 0.5
                
                if index is not None and 0 <= index < len(chunks):
                    chunk_with_score = chunks[index].copy()
                    # Normalize Cohere relevance score (usually 0-1, but ensure it's in range)
                    chunk_with_score["score"] = max(0.0, min(1.0, float(relevance_score)))
                    reranked_chunks.append(chunk_with_score)
            
            return reranked_chunks if reranked_chunks else chunks[:top_k]
        except Exception as e:
            logger.error(f"❌ Cohere rerank API error: {e}")
            return chunks[:top_k]
    
    def _rerank_bge(self, query: str, chunks: List[Dict], top_k: int) -> List[Dict]:
        """Rerank using BGE reranker."""
        if not hasattr(self, '_bge_model') or not hasattr(self, '_bge_tokenizer'):
            return chunks[:top_k]
        
        try:
            import torch
            
            device = getattr(self, '_bge_device', 'cpu')
            
            # Prepare pairs
            pairs = []
            for chunk in chunks:
                chunk_text = chunk.get("text", chunk.get("content", ""))
                pairs.append([query, chunk_text])
            
            # Tokenize and get scores
            with torch.no_grad():
                inputs = self._bge_tokenizer(
                    pairs,
                    padding=True,
                    truncation=True,
                    return_tensors='pt',
                    max_length=512
                )
                # Move inputs to device
                inputs = {k: v.to(device) for k, v in inputs.items()}
                scores = self._bge_model(**inputs, return_dict=True).logits.view(-1, ).float()
                scores = scores.cpu().tolist()
            
            # Normalize scores to [0, 1] range if needed
            if len(scores) > 0:
                min_score = min(scores)
                max_score = max(scores)
                if max_score > min_score:
                    scores = [(s - min_score) / (max_score - min_score) for s in scores]
                else:
                    scores = [0.5] * len(scores)
            
            # Combine chunks with scores
            scored_chunks = []
            for chunk, score in zip(chunks, scores):
                chunk_with_score = chunk.copy()
                chunk_with_score["score"] = float(score)
                scored_chunks.append(chunk_with_score)
            
            # Sort by score (descending)
            scored_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            return scored_chunks[:top_k]
        except Exception as e:
            logger.error(f"❌ BGE reranking error: {e}")
            return chunks[:top_k]
    
    def _rerank_llm(self, query: str, chunks: List[Dict], top_k: int) -> List[Dict]:
        """Rerank using LLM-based approach."""
        if not self._llm_reranker_available:
            return chunks[:top_k]

        if len(chunks) < 10:
            return chunks[:top_k]

        try:
            from .mistral import call_mistral_chat
            
            # Create a prompt for LLM to rank chunks
            chunk_texts = []
            for i, chunk in enumerate(chunks):
                chunk_text = chunk.get("text", chunk.get("content", ""))
                chunk_texts.append(f"Chunk {i+1}:\n{chunk_text[:500]}...")  # Limit length
            
            prompt = f"""You are a ranking assistant. Given a query and a list of document chunks, rank them by relevance.

Query: {query}

Chunks:
{chr(10).join(chunk_texts)}

Return ONLY a comma-separated list of chunk numbers (1-{len(chunks)}) in order of relevance, most relevant first.
Example: 3,1,5,2,4

Ranking:"""
            
            api_key = settings.MISTRAL_API_KEY
            model = settings.MISTRAL_MODEL
            
            result = call_mistral_chat(prompt, api_key, model)
            ranking_text = result.get("content", "").strip()
            
            # Parse ranking
            try:
                # Extract numbers from response
                import re
                numbers = re.findall(r'\d+', ranking_text)
                ranked_indices = [int(n) - 1 for n in numbers if 1 <= int(n) <= len(chunks)]
                
                # Remove duplicates while preserving order
                seen = set()
                unique_indices = []
                for idx in ranked_indices:
                    if idx not in seen and 0 <= idx < len(chunks):
                        seen.add(idx)
                        unique_indices.append(idx)
                
                # Add any missing chunks at the end
                for i in range(len(chunks)):
                    if i not in seen:
                        unique_indices.append(i)
                
                # Create chunks with scores based on ranking position
                reranked_chunks = []
                for rank, idx in enumerate(unique_indices[:top_k]):
                    chunk_with_score = chunks[idx].copy()
                    # Higher rank = higher score (inverse of rank position)
                    chunk_with_score["score"] = 1.0 - (rank / max(len(unique_indices), 1))
                    reranked_chunks.append(chunk_with_score)
                return reranked_chunks
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse LLM ranking: {e}. Using original order.")
                return chunks[:top_k]
        except Exception as e:
            logger.error(f"❌ LLM reranking error: {e}")
            return chunks[:top_k]
    
    def _apply_advanced_scoring(self, query: str, chunks: List[Dict], top_k: int) -> List[Dict]:
        """
        Apply advanced scoring to reranked chunks:
        - Boost exact matches
        - Boost section matches
        - Penalize generic chunks
        
        Args:
            query: The search query
            chunks: List of chunks with initial scores
            top_k: Number of top chunks to return
        
        Returns:
            List of top-k chunks with enhanced scores
        """
        if not chunks:
            return []
        
        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        scored_chunks = []
        
        for chunk in chunks:
            chunk_text = chunk.get("text", chunk.get("content", ""))
            chunk_lower = chunk_text.lower()
            
            # Start with base score (if available) or 0.5
            base_score = chunk.get("score", 0.5)
            if not isinstance(base_score, (int, float)):
                base_score = 0.5
            
            # Calculate enhancement scores
            exact_match_score = self._calculate_exact_match_score(query, query_lower, chunk_text, chunk_lower)
            section_match_score = self._calculate_section_match_score(query, chunk_text)
            generic_penalty = self._calculate_generic_penalty(chunk_text, chunk_lower)
            
            # Apply boosts and penalties
            # Boost exact matches (up to +0.3)
            # Boost section matches (up to +0.2)
            # Penalize generic chunks (up to -0.3)
            enhanced_score = base_score + exact_match_score * 0.3 + section_match_score * 0.2 - generic_penalty * 0.3
            
            # Ensure score is in valid range [0, 1]
            enhanced_score = max(0.0, min(1.0, enhanced_score))
            
            scored_chunks.append({
                "chunk": chunk,
                "base_score": base_score,
                "enhanced_score": enhanced_score,
                "exact_match_boost": exact_match_score,
                "section_match_boost": section_match_score,
                "generic_penalty": generic_penalty
            })
        
        # Sort by enhanced score (descending)
        scored_chunks.sort(key=lambda x: x["enhanced_score"], reverse=True)
        
        # Return top-k chunks (restore original chunk structure)
        result = []
        for item in scored_chunks[:top_k]:
            chunk = item["chunk"].copy()
            # Store scoring metadata for debugging
            chunk["_rerank_metadata"] = {
                "base_score": item["base_score"],
                "enhanced_score": item["enhanced_score"],
                "exact_match_boost": item["exact_match_boost"],
                "section_match_boost": item["section_match_boost"],
                "generic_penalty": item["generic_penalty"]
            }
            result.append(chunk)
        
        return result
    
    def _calculate_exact_match_score(self, query: str, query_lower: str, chunk_text: str, chunk_lower: str) -> float:
        """
        Calculate exact match score (0.0 to 1.0).
        Higher score for exact phrase matches and important word matches.
        """
        score = 0.0
        
        # 1. Exact phrase match (highest boost)
        if query_lower in chunk_lower:
            score += 0.8
        elif query in chunk_text:  # Case-sensitive match
            score += 0.9
        
        # 2. All query words present (medium boost)
        query_words = set(re.findall(r'\b\w{3,}\b', query_lower))  # Words with 3+ chars
        chunk_words = set(re.findall(r'\b\w{3,}\b', chunk_lower))
        
        if query_words:
            words_matched = len(query_words & chunk_words)
            words_ratio = words_matched / len(query_words)
            score += words_ratio * 0.5
        
        # 3. Consecutive word matches (boost)
        query_word_list = query_lower.split()
        if len(query_word_list) >= 2:
            for i in range(len(query_word_list) - 1):
                bigram = f"{query_word_list[i]} {query_word_list[i+1]}"
                if bigram in chunk_lower:
                    score += 0.2
                    break  # Only count once
        
        return min(1.0, score)
    
    def _calculate_section_match_score(self, query: str, chunk_text: str) -> float:
        """
        Calculate section match score (0.0 to 1.0).
        Higher score if chunk contains section references from query.
        """
        score = 0.0
        
        try:
            from ..application.query_expansion.mappings import find_sections_in_query, get_section_info
            
            # Find sections in query
            query_sections = find_sections_in_query(query)
            
            if not query_sections:
                return 0.0
            
            chunk_lower = chunk_text.lower()
            
            # Check if chunk mentions any of the query sections
            for section in query_sections:
                section_lower = section.lower()
                
                # Direct section mention
                if section_lower in chunk_lower:
                    score += 0.6
                
                # Section number match (e.g., "section 16" or "sec 16")
                section_num = re.search(r'section\s+(\d+)', section_lower)
                if section_num:
                    num = section_num.group(1)
                    # Check for various section formats
                    patterns = [
                        rf'section\s+{num}\b',
                        rf'sec\s+{num}\b',
                        rf's\.\s*{num}\b',
                        rf'section\s+{num}[a-z]?\b'
                    ]
                    for pattern in patterns:
                        if re.search(pattern, chunk_lower, re.IGNORECASE):
                            score += 0.4
                            break
                
                # Section title/keywords match
                section_info = get_section_info(section)
                if section_info:
                    # Check for section title
                    title = section_info.get("title", "").lower()
                    if title and title in chunk_lower:
                        score += 0.3
                    
                    # Check for section keywords
                    keywords = section_info.get("keywords", [])
                    for keyword in keywords[:3]:
                        if keyword.lower() in chunk_lower:
                            score += 0.1
                            break
            
        except ImportError:
            # Mappings not available, use basic pattern matching
            section_pattern = r'section\s+\d+'
            query_sections = re.findall(section_pattern, query, re.IGNORECASE)
            if query_sections:
                chunk_lower = chunk_text.lower()
                for section in query_sections:
                    if section.lower() in chunk_lower:
                        score += 0.5
        except Exception as e:
            logger.debug(f"Error calculating section match score: {e}")
        
        return min(1.0, score)
    
    def _calculate_generic_penalty(self, chunk_text: str, chunk_lower: str) -> float:
        """
        Calculate generic chunk penalty (0.0 to 1.0).
        Higher penalty for generic, non-specific chunks.
        """
        penalty = 0.0
        
        # Generic phrases that indicate low specificity
        generic_phrases = [
            "for more information",
            "please refer to",
            "see also",
            "note that",
            "it is important",
            "generally speaking",
            "in general",
            "as a rule",
            "typically",
            "usually",
            "may be",
            "can be",
            "should be",
            "might be",
            "could be",
            "this document",
            "the following",
            "above mentioned",
            "as mentioned",
            "as stated"
        ]
        
        # Check for generic phrases
        generic_count = 0
        for phrase in generic_phrases:
            if phrase in chunk_lower:
                generic_count += 1
        
        if generic_count > 0:
            penalty += min(0.5, generic_count * 0.1)
        
        # Penalize very short chunks (likely incomplete)
        word_count = len(chunk_text.split())
        if word_count < 5:
            penalty += 0.1
        elif word_count < 20:
            penalty += 0.1
        
        # Penalize chunks with too many generic words
        generic_words = ["the", "a", "an", "is", "are", "was", "were", "be", "been", "being"]
        words = chunk_lower.split()
        generic_word_ratio = sum(1 for w in words if w in generic_words) / max(len(words), 1)
        if generic_word_ratio > 0.3:  # More than 30% generic words
            penalty += 0.2
        
        # Penalize chunks without specific terms (numbers, proper nouns, technical terms)
        # Check for numbers, capital letters (proper nouns), technical terms
        has_numbers = bool(re.search(r'\d+', chunk_text))
        has_capitals = bool(re.search(r'\b[A-Z][a-z]+\b', chunk_text))
        has_technical = bool(re.search(r'\b(gst|itc|section|rule|form|return|tax|credit|refund|registration)\b', chunk_lower))
        
        specific_indicators = sum([has_numbers, has_capitals, has_technical])
        if specific_indicators == 0:
            penalty += 0.3
        elif specific_indicators == 1:
            penalty += 0.1
        
        return min(1.0, penalty)


# Global singleton instance
_reranking_service = None


def get_reranking_service() -> RerankingService:
    """Get or create the global reranking service instance."""
    global _reranking_service
    if _reranking_service is None:
        _reranking_service = RerankingService()
    return _reranking_service

