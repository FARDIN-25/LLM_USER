"""
Comprehensive Query Expansion Service
Supports multiple expansion strategies:
1. Static keyword dictionary expansion
2. Dynamic LLM-based expansion
3. Synonym injection
4. Module-wise expansion
5. Token-optimized expansion
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from enum import Enum
from src.shared.config import settings

import spacy

_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load('en_core_web_sm')
        except Exception:
            _nlp = None
    return _nlp

logger = logging.getLogger("fintax")


class ExpansionStrategy(str, Enum):
    """Supported expansion strategies."""
    static = "static"  # Static keyword dictionary
    llm = "llm"  # Dynamic LLM-based
    hybrid = "hybrid"  # Combined static + LLM
    module_wise = "module_wise"  # Module-specific expansion
    token_optimized = "token_optimized"  # Token-optimized expansion


def parse_strategy(value: Optional[str]) -> ExpansionStrategy:
    """Safely parse expansion strategy string to enum. Returns static on invalid/None."""
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ExpansionStrategy.static
        return ExpansionStrategy(str(value).strip().lower())
    except (ValueError, AttributeError, TypeError):
        return ExpansionStrategy.static


class QueryExpansionService:
    """Unified query expansion service supporting multiple strategies."""
    
    def __init__(self):
        self._static_expansion_available = False
        self._llm_expansion_available = False
        self._available_strategies = set()
        
        # Initialize expansion capabilities
        self._initialize_expansion()
    
    def _initialize_expansion(self):
        """Initialize all expansion capabilities."""
        # 1. Static expansion (keyword dictionary)
        self._init_static_expansion()
        
        # 2. LLM-based expansion
        self._init_llm_expansion()
        
        logger.info(f"✅ Query expansion service initialized. Available strategies: {self._available_strategies}")
    
    def _init_static_expansion(self):
        """Initialize static keyword dictionary expansion."""
        try:
            from .query_expansion.tax_vocabulary import expand_query as static_expand
            # Test if it works
            test_result = static_expand("test")
            if isinstance(test_result, dict) and "expanded_queries" in test_result:
                self._static_expand_func = static_expand
                self._static_expansion_available = True
                self._available_strategies.add(ExpansionStrategy.static)
                self._available_strategies.add(ExpansionStrategy.hybrid)
                self._available_strategies.add(ExpansionStrategy.module_wise)
                self._available_strategies.add(ExpansionStrategy.token_optimized)
                logger.info("✅ Static expansion (keyword dictionary) available")
        except ImportError as e:
            logger.warning(f"⚠️ Static expansion module not available: {e}")
        except Exception as e:
            logger.error(f"❌ Static expansion initialization failed: {e}", exc_info=True)
    
    def _init_llm_expansion(self):
        """Initialize LLM-based dynamic expansion."""
        try:
            mistral_key = settings.MISTRAL_API_KEY
            if mistral_key:
                self._llm_expansion_available = True
                self._available_strategies.add(ExpansionStrategy.llm)
                self._available_strategies.add(ExpansionStrategy.hybrid)
                logger.info("✅ LLM-based expansion available")
            else:
                logger.warning("⚠️ MISTRAL_MODEL not set. LLM-based expansion unavailable.")
        except Exception as e:
            logger.error(f"❌ LLM expansion initialization failed: {e}", exc_info=True)
    
    def is_available(self, strategy: Optional[ExpansionStrategy] = None) -> bool:
        """Check if a specific expansion strategy is available."""
        if strategy is None:
            return len(self._available_strategies) > 0
        return strategy in self._available_strategies
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available expansion strategies."""
        return [s.value for s in self._available_strategies]
    
    async def expand(
        self,
        query: str,
        strategy: Optional[ExpansionStrategy] = None,
        max_tokens: int = 200,
        use_important_words: bool = True
    ) -> Dict:
        """
        Expand query using the specified strategy.
        
        Args:
            query: The user query to expand
            strategy: Expansion strategy to use. If None, uses hybrid (best available).
            max_tokens: Maximum tokens for token-optimized expansion
            use_important_words: Whether to extract important words for highlighting
        
        Returns:
            Dictionary with expanded_queries, important_words, and metadata
        """
        if not query or not query.strip():
            return {
                "expanded_queries": [query],
                "important_words": [],
                "strategy_used": "none"
            }
        
        # Determine strategy
        if strategy is None:
            # Use hybrid if available, otherwise use first available
            if ExpansionStrategy.hybrid in self._available_strategies:
                strategy = ExpansionStrategy.hybrid
            elif ExpansionStrategy.static in self._available_strategies:
                strategy = ExpansionStrategy.static
            elif ExpansionStrategy.llm in self._available_strategies:
                strategy = ExpansionStrategy.llm
            else:
                logger.warning("⚠️ No expansion strategies available. Returning original query.")
                return {
                    "expanded_queries": [query],
                    "important_words": [],
                    "strategy_used": "none"
                }
        
        # Route to appropriate expansion method
        try:
            if strategy == ExpansionStrategy.static:
                return self._expand_static(query, use_important_words)
            elif strategy == ExpansionStrategy.llm:
                return await self._expand_llm(query, use_important_words)
            elif strategy == ExpansionStrategy.hybrid:
                return await self._expand_hybrid(query, use_important_words)
            elif strategy == ExpansionStrategy.module_wise:
                return self._expand_module_wise(query, use_important_words)
            elif strategy == ExpansionStrategy.token_optimized:
                return self._expand_token_optimized(query, max_tokens, use_important_words)
            else:
                logger.warning(f"⚠️ Unknown expansion strategy: {strategy}. Using static.")
                return self._expand_static(query, use_important_words)
        except Exception as e:
            logger.error(f"❌ Query expansion failed with {strategy}: {e}", exc_info=True)
            # Fallback to original query
            return {
                "expanded_queries": [query],
                "important_words": [],
                "strategy_used": "error",
                "error": str(e)
            }
    
    def _expand_static(self, query: str, use_important_words: bool) -> Dict:
        """Expand using static keyword dictionary with comprehensive mappings."""
        if not self._static_expansion_available:
            return {
                "expanded_queries": [query],
                "important_words": [],
                "strategy_used": "static"
            }
        
        try:
            # Get base expansion from tax vocabulary
            result = self._static_expand_func(query)
            
            # Normalize result shape (tax_vocabulary may return dict or wrong shape)
            if not isinstance(result, dict):
                return {
                    "expanded_queries": [query],
                    "important_words": [],
                    "strategy_used": "static",
                    "error": "Invalid result shape from expand_query"
                }
            
            # Extract expanded queries (ensure list of strings)
            expanded_queries = result.get("expanded_queries", [query])
            if not isinstance(expanded_queries, list):
                expanded_queries = [query]
            expanded_queries = [
                (str(x).strip() or query) for x in expanded_queries
                if x is not None
            ][:10]
            if not expanded_queries:
                expanded_queries = [query]
            
            # Apply comprehensive mappings
            enhanced_expansions = self._apply_comprehensive_mappings(query, expanded_queries)
            
            # Extract important words if requested (ensure list of strings)
            important_words = []
            if use_important_words:
                raw_words = result.get("important_words", [])
                if isinstance(raw_words, list):
                    important_words = [str(w).strip() for w in raw_words if w is not None and str(w).strip()]
                # Add mapped terms to important words
                important_words.extend(self._extract_mapped_keywords(query, enhanced_expansions))
                important_words = list(dict.fromkeys(important_words))[:30]  # Deduplicate preserving order
            
            return {
                "expanded_queries": enhanced_expansions[:5] if enhanced_expansions else [query],  # Limit to top 5
                "important_words": important_words,
                "strategy_used": "static",
                "matched_concepts": result.get("matched_concepts", []),
                "mappings_applied": {
                    "sections": self._find_sections(query),
                    "forms": self._find_forms(query),
                    "acronyms": self._find_acronyms(query),
                    "legal_aliases": self._find_legal_aliases(query)
                }
            }
        except Exception as e:
            logger.error(f"❌ Static expansion error: {e}")
            return {
                "expanded_queries": [query],
                "important_words": [],
                "strategy_used": "static",
                "error": str(e)
            }
    
    def _apply_comprehensive_mappings(self, query: str, base_expansions: List[str]) -> List[str]:
        """Apply comprehensive mappings: sections, chapters, forms, acronyms, legal aliases."""
        enhanced = set(base_expansions)
        query_lower = query.lower()
        
        try:
            from .query_expansion.mappings import (
                get_section_info, get_chapter_info, get_form_info,
                expand_acronym, get_legal_aliases,
                find_sections_in_query, find_forms_in_query, find_acronyms_in_query
            )
            
            # 1. Section mapping
            sections = find_sections_in_query(query)
            for section in sections:
                section_info = get_section_info(section)
                if section_info:
                    enhanced.add(f"{query} {section_info['title']}")
                    for alias in section_info.get("aliases", [])[:3]:
                        enhanced.add(f"{query} {alias}")
                    for keyword in section_info.get("keywords", [])[:3]:
                        enhanced.add(f"{query} {keyword}")
            
            # 2. Chapter mapping
            chapter_patterns = [r'chapter\s+([ivx]+)', r'chapter\s+(\d+)']
            for pattern in chapter_patterns:
                matches = re.findall(pattern, query_lower, re.IGNORECASE)
                for match in matches:
                    chapter = f"chapter {match}"
                    chapter_info = get_chapter_info(chapter)
                    if chapter_info:
                        enhanced.add(f"{query} {chapter_info['title']}")
                        for keyword in chapter_info.get("keywords", [])[:3]:
                            enhanced.add(f"{query} {keyword}")
            
            # 3. Form mapping
            forms = find_forms_in_query(query)
            for form in forms:
                form_info = get_form_info(form)
                if form_info:
                    enhanced.add(f"{query} {form_info['title']}")
                    for alias in form_info.get("aliases", [])[:3]:
                        enhanced.add(f"{query} {alias}")
            
            # 4. Acronym expansion
            acronyms = find_acronyms_in_query(query)
            for acronym in acronyms:
                expansion = expand_acronym(acronym)
                if expansion:
                    enhanced.add(f"{query} {expansion}")
                    # Also add expanded version
                    enhanced.add(query.replace(acronym, expansion))
            
            # 5. Spacy NLP Processing (Tokenization, Lemmatization, Noun Phrases, Entities)
            nlp = get_nlp()
            if nlp:
                doc = nlp(query_lower)
                
                # Tokenization & Lemmatization
                for token in doc:
                    if not token.is_stop and not token.is_punct and len(token.text) > 2:
                        enhanced.add(token.lemma_)
                        enhanced.add(f"{query} {token.lemma_}")
                    
                    # Legal aliases
                    if len(token.text) > 3:
                        aliases = get_legal_aliases(token.text)
                        for alias in aliases[:2]:
                            enhanced.add(alias)
                            enhanced.add(f"{query} {alias}")
                            
                # Noun Phrase Extraction
                for chunk in doc.noun_chunks:
                    chunk_text = chunk.text.strip()
                    if chunk_text:
                        enhanced.add(chunk_text)
                        enhanced.add(f"{query} {chunk_text}")
                        
                # Named Entity Recognition
                for ent in doc.ents:
                    ent_text = ent.text.strip()
                    if ent_text:
                        enhanced.add(ent_text)
                        enhanced.add(f"{query} {ent_text}")
            else:
                # Fallback to old split
                words = query_lower.split()
                for word in words:
                    if len(word) > 3:  # Skip short words
                        aliases = get_legal_aliases(word)
                        for alias in aliases[:2]:
                            enhanced.add(f"{query} {alias}")
            
            # 6. Synonym injection (from TAX_SYNONYMS)
            try:
                from .query_expansion.tax_vocabulary import TAX_SYNONYMS
                for term, synonyms in TAX_SYNONYMS.items():
                    if term in query_lower:
                        for synonym in synonyms[:2]:
                            enhanced.add(f"{query} {synonym}")
            except:
                pass
            
        except ImportError as e:
            logger.warning(f"⚠️ Comprehensive mappings not available: {e}")
        except Exception as e:
            logger.error(f"❌ Error applying comprehensive mappings: {e}")
        
        return list(enhanced)[:10]  # Return top 10 expansions
    
    def _find_sections(self, query: str) -> List[str]:
        """Find sections in query."""
        try:
            from .query_expansion.mappings import find_sections_in_query
            return find_sections_in_query(query)
        except:
            return []
    
    def _find_forms(self, query: str) -> List[str]:
        """Find forms in query."""
        try:
            from .query_expansion.mappings import find_forms_in_query
            return find_forms_in_query(query)
        except:
            return []
    
    def _find_acronyms(self, query: str) -> List[str]:
        """Find acronyms in query."""
        try:
            from .query_expansion.mappings import find_acronyms_in_query
            return find_acronyms_in_query(query)
        except:
            return []
    
    def _find_legal_aliases(self, query: str) -> List[str]:
        """Find legal aliases in query."""
        try:
            from .query_expansion.mappings import get_legal_aliases
            aliases = []
            nlp = get_nlp()
            if nlp:
                doc = nlp(query.lower())
                words = [token.text for token in doc if not token.is_punct]
            else:
                words = query.lower().split()
                
            for word in words:
                if len(word) > 3:
                    word_aliases = get_legal_aliases(word)
                    aliases.extend(word_aliases)
            return list(set(aliases))[:10]
        except:
            return []
    
    def _extract_mapped_keywords(self, query: str, expansions: List[str]) -> List[str]:
        """Extract keywords from mapped expansions."""
        keywords = []
        try:
            from .query_expansion.mappings import (
                get_section_info, get_form_info, expand_acronym
            )
            
            # Extract from sections
            sections = self._find_sections(query)
            for section in sections:
                section_info = get_section_info(section)
                if section_info:
                    keywords.append(section_info.get("title", ""))
                    keywords.extend(section_info.get("keywords", [])[:3])
            
            # Extract from forms
            forms = self._find_forms(query)
            for form in forms:
                form_info = get_form_info(form)
                if form_info:
                    keywords.append(form_info.get("title", ""))
            
            # Extract from acronyms
            acronyms = self._find_acronyms(query)
            for acronym in acronyms:
                expansion = expand_acronym(acronym)
                if expansion:
                    keywords.append(expansion)
            
        except:
            pass
        
        return [k for k in keywords if k and len(k) > 2]
    
    async def _expand_llm(self, query: str, use_important_words: bool) -> Dict:
        """Expand using LLM-based dynamic expansion."""
        if not self._llm_expansion_available:
            return {
                "expanded_queries": [query],
                "important_words": [],
                "strategy_used": "llm"
            }
        
        try:
            from ..infrastructure.mistral import async_call_mistral_chat
            
            prompt = f"""You are a query expansion assistant for a tax and GST knowledge base. 
Given a user query, expand it with relevant synonyms, related terms, and domain-specific keywords that would help find relevant documents.

User Query: {query}

Provide an expanded version of this query that includes:
1. Synonyms and related terms (e.g., "GST" → "GST, Goods and Services Tax, tax")
2. Relevant section numbers if applicable
3. Related concepts and terminology
4. Alternative phrasings

Return ONLY the expanded query text, nothing else. Keep it concise (max 100 words).

Expanded Query:"""
            
            api_key = settings.MISTRAL_API_KEY
            model = settings.MISTRAL_MODEL
            
            result = await async_call_mistral_chat(prompt, api_key, model)
            expanded_text = result.get("content", "").strip()
            
            # Clean up the response
            expanded_text = expanded_text.replace("Expanded Query:", "").strip()
            expanded_text = expanded_text.split("\n")[0].strip()  # Take first line only
            
            if not expanded_text or len(expanded_text) < len(query):
                expanded_text = query
            
            # Extract important words from expanded query
            important_words = []
            if use_important_words:
                nlp = get_nlp()
                if nlp:
                    doc = nlp(expanded_text.lower())
                    important_words = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct and len(token.text) > 3][:10]
                else:
                    words = expanded_text.lower().split()
                    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
                    important_words = [w for w in words if len(w) > 3 and w not in stopwords][:10]
            
            return {
                "expanded_queries": [expanded_text],
                "important_words": important_words,
                "strategy_used": "llm"
            }
        except Exception as e:
            logger.error(f"❌ LLM expansion error: {e}")
            return {
                "expanded_queries": [query],
                "important_words": [],
                "strategy_used": "llm",
                "error": str(e)
            }
    
    async def _expand_hybrid(self, query: str, use_important_words: bool) -> Dict:
        """Expand using hybrid approach (static + LLM) with comprehensive mappings."""
        # Start with static expansion (includes comprehensive mappings)
        static_result = self._expand_static(query, use_important_words)
        
        # If LLM is available, enhance with LLM expansion
        if self._llm_expansion_available:
            try:
                llm_result = await self._expand_llm(query, use_important_words)
                
                # Combine expanded queries (prioritize LLM, then static)
                llm_expanded = llm_result.get("expanded_queries", [query])
                static_queries = static_result.get("expanded_queries", [])
                
                # Filter out original query from static to avoid duplicates
                static_filtered = [q for q in static_queries if q != query]
                
                # Combine: LLM first, then static
                expanded_queries = llm_expanded + static_filtered
                
                # Merge important words
                important_words = list(set(
                    static_result.get("important_words", []) + 
                    llm_result.get("important_words", [])
                ))[:25]  # Limit to 25 words
                
                return {
                    "expanded_queries": expanded_queries[:8],  # Limit to top 8 to ensure LLM is included
                    "important_words": important_words,
                    "strategy_used": "hybrid",
                    "matched_concepts": static_result.get("matched_concepts", []),
                    "mappings_applied": static_result.get("mappings_applied", {})
                }
            except Exception as e:
                logger.warning(f"⚠️ LLM expansion failed in hybrid mode: {e}. Using static only.")
        
        return static_result
    
    def _expand_module_wise(self, query: str, use_important_words: bool) -> Dict:
        """Expand using module-wise approach (domain-specific modules) with comprehensive mappings."""
        # Start with static expansion (includes comprehensive mappings)
        static_result = self._expand_static(query, use_important_words)
        
        # Enhance with module-specific terms
        try:
            # Detect which module(s) the query relates to
            query_lower = query.lower()
            module_keywords = {
                "gst": ["gst", "goods and services tax", "vat", "cgst", "sgst", "igst"],
                "income_tax": ["income tax", "itr", "tds", "tds return"],
                "compliance": ["compliance", "return", "filing", "due date"],
                "registration": ["registration", "gstin", "register", "enrollment"]
            }
            
            detected_modules = []
            for module, keywords in module_keywords.items():
                if any(kw in query_lower for kw in keywords):
                    detected_modules.append(module)
            
            # Add module-specific expansions
            expanded_queries = static_result.get("expanded_queries", [query])
            important_words = static_result.get("important_words", [])

            
            # Add module context to important words
            if detected_modules:
                important_words.extend(detected_modules)
                important_words = list(set(important_words))[:20]
            
            return {
                "expanded_queries": expanded_queries,
                "important_words": important_words,
                "strategy_used": "module_wise",
                "detected_modules": detected_modules,
                "matched_concepts": static_result.get("matched_concepts", [])
            }
        except Exception as e:
            logger.error(f"❌ Module-wise expansion error: {e}")
            return static_result
    
    def _expand_token_optimized(self, query: str, max_tokens: int, use_important_words: bool) -> Dict:
        """Expand with token optimization (limit expansion to fit token budget) using comprehensive mappings."""
        # Get base expansion (includes comprehensive mappings)
        base_result = self._expand_static(query, use_important_words)
        expanded_queries = base_result.get("expanded_queries", [query])
        important_words = base_result.get("important_words", [])
        
        # Estimate tokens (rough: 1 token ≈ 4 characters)
        def estimate_tokens(text: str) -> int:
            return len(text) // 4
        
        # Filter and optimize expanded queries to fit token budget
        optimized_queries = []
        total_tokens = 0
        
        # Always include original query
        if query not in optimized_queries:
            query_tokens = estimate_tokens(query)
            if total_tokens + query_tokens <= max_tokens:
                optimized_queries.append(query)
                total_tokens += query_tokens
        
        # Add other expansions if they fit
        for exp_query in expanded_queries:
            if exp_query == query:
                continue
            
            exp_tokens = estimate_tokens(exp_query)
            if total_tokens + exp_tokens <= max_tokens:
                optimized_queries.append(exp_query)
                total_tokens += exp_tokens
            else:
                # Try to truncate if close
                if total_tokens + exp_tokens <= max_tokens * 1.2:
                    # Truncate to fit
                    remaining_tokens = max_tokens - total_tokens
                    max_chars = remaining_tokens * 4
                    truncated = exp_query[:max_chars].rsplit(' ', 1)[0]  # Don't cut words
                    if truncated and truncated not in optimized_queries:
                        optimized_queries.append(truncated)
                        total_tokens += estimate_tokens(truncated)
                break
        
        # If no expansions fit, use original query
        if not optimized_queries:
            optimized_queries = [query]
        
        return {
            "expanded_queries": optimized_queries,
            "important_words": important_words[:15],  # Limit important words too
            "strategy_used": "token_optimized",
            "tokens_used": total_tokens,
            "max_tokens": max_tokens,
            "matched_concepts": base_result.get("matched_concepts", [])
        }


# Global singleton instance
_expansion_service = None


def get_expansion_service() -> QueryExpansionService:
    """Get or create the global query expansion service instance."""
    global _expansion_service
    if _expansion_service is None:
        _expansion_service = QueryExpansionService()
    return _expansion_service

