import logging
import time
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
# search_logic imports removed as indices are now in DB

logger = logging.getLogger("fintax")

class SearchService:
    """
    Singleton service to manage Search logic state.
    BM25 is now handled by PostgreSQL FTS, so this service no longer loads docs into RAM.
    """
    _instance: Optional['SearchService'] = None
    
    def __init__(self):
        self.sparse_retriever = None # No longer used
        self.is_initialized = False
        self.doc_count = 0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SearchService()
        return cls._instance

    def initialize(self, db: Session):
        """
        No-op initialization now that search is DB-resident.
        """
        if self.is_initialized:
            return
        logger.info("🚀 SearchService: Initialized (PostgreSQL FTS mode)")
        self.is_initialized = True

    def get_retriever(self) -> Optional[Any]:
        """Returns None as FTS is used directly in search_logic."""
        return None

    def refresh_index(self, db: Session):
        """No-op as FTS index is managed by PostgreSQL."""
        pass

# Global Accessor
def get_search_service():
    return SearchService.get_instance()
