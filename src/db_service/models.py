from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, JSON, ARRAY, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, event
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from .database import Base
import enum
import hashlib

# ============================================================================
# ENUM CLASSES FOR CONSTRAINED VALUES
# ============================================================================

class PlanTypeEnum(str, enum.Enum):
    """Enumeration for subscription plan types."""
    FREE = "Free"
    PRO = "Pro"
    ENTERPRISE = "Enterprise"


class FolderAssignmentEnum(str, enum.Enum):
    """Enumeration for folder assignment types."""
    GST = "GST"
    IT = "IT"
    ETC = "ETC"


# ============================================================================
# PHASE 1: NEW MODELS - Foundation & Database Schema Updates
# ============================================================================

class ChatSession(Base):
    """
    Chat session. history JSON stores: {"title": "Short generated title", "first_question": "User first message"}.
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    # user_id stores authenticated user's email (unique identifier from JWT). String type; no schema change.
    user_id = Column(String(100), nullable=False, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)  # Unique session identifier
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)  # Auto-set on creation
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update on modification
    # Fintax-style sidebar: title and first question stored here (no new tables)
    history = Column(JSON, nullable=True)  # PostgreSQL: JSONB via migration. Structure: {"title": "...", "first_question": "..."}. Default '{}' in DB.
    is_temporary = Column(Boolean, default=False, nullable=False)  # Temporary chat sessions (e.g. quick try without saving to sidebar)
    session_metadata = Column(JSON, nullable=True)  # Rich JSON user profile/metadata context


class ChatMessage(Base):
    
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), ForeignKey("chat_sessions.session_id"), nullable=False, index=True)  # Foreign key to ChatSession
    query_id = Column(Integer, ForeignKey("user_queries.id"), nullable=False, index=True)  # Foreign key to UserQuery
    response_id = Column(Integer, ForeignKey("query_responses.id"), nullable=False, index=True)  # Foreign key to QueryResponse
    react = Column(String(20), default="no_react", nullable=False, index=True)  # Single emoji reaction; "no_react" = none
    tags = Column(JSON, nullable=True, index=True)  # JSON array of tags (e.g., ["important", "tax"])
    feedback = Column(String(10), nullable=True)  # 'up', 'down', or null for user feedback
    # JSON metadata: {"hidden": true} when message is after an edited query (no physical delete). Column name "metadata" in DB.
    message_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)  # Auto-set on creation


# MessageReaction table removed: single emoji stored in chat_messages.react (VARCHAR), default "no_react"


class Subscription(Base):
    
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    # user_id = authenticated email (unique identifier). String(100) for consistency with JWT subject.
    user_id = Column(String(100), nullable=False, index=True)
    plan_type = Column(String(20), nullable=False, default="Free")  # Plan type: Free, Pro, Enterprise
    features = Column(JSON, nullable=True)  # JSON object for plan features
    usage_limits = Column(JSON, nullable=True)  # JSON object for usage limits
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)  # Auto-set on creation
    expires_at = Column(TIMESTAMP, nullable=True)  # Expiration date (null for lifetime plans)


class FileUpload(Base):
    
    __tablename__ = "file_uploads"

    id = Column(Integer, primary_key=True, index=True)
    # user_id = authenticated email (unique identifier). String type unchanged.
    user_id = Column(String(100), nullable=False, index=True)
    session_id = Column(String(100), ForeignKey("chat_sessions.session_id"), nullable=True, index=True)  # Foreign key to ChatSession (optional)
    file_path = Column(String(1000), nullable=False)  # Path to uploaded file
    file_type = Column(String(50), nullable=True)  # File type (PDF, CSV, TXT, etc.)
    tags = Column(String(50), nullable=True, index=True)  # Category: GST, IT, ETC (DB column name: tags)
    uploaded_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)  # Auto-set on creation


# ============================================================================
# PHASE 1: UPDATED EXISTING MODELS
# ============================================================================

class UserQuery(Base):
    
    __tablename__ = "user_queries"

    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    # user_id = authenticated email when present; nullable for legacy/anonymous. String(100).
    user_id = Column(String(100), nullable=True)
    session_id = Column(String(100), ForeignKey("chat_sessions.session_id"), nullable=True, index=True)  # Foreign key to ChatSession
    is_temporary = Column(Boolean, default=False, nullable=False)  # NEW: Flag for temporary queries
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    language = Column(String(10), nullable=True)
    query_metadata = Column(JSON, nullable=True)
    # Automatic topic clustering (no new tables): GST / INCOME_TAX / TDS / ROC / GENERAL
    category = Column(String(50), nullable=True, index=True, default="GENERAL")


class QueryResponse(Base):

    __tablename__ = "query_responses"

    id = Column(Integer, primary_key=True, index=True)
    # Link to user_queries; cascade delete so orphaned responses are not left behind
    query_id = Column(
        Integer,
        ForeignKey("user_queries.id", ondelete="CASCADE"),
        nullable=False,
    )
    response_text = Column(Text, nullable=False)

    # Retrieval / timing / model metadata
    # Unified IDs: ["docs_123", "book_456"]
    retrieved_context_ids = Column(ARRAY(String), nullable=True)
    llm_model = Column(String(100), nullable=True)
    latency_ms = Column(Integer, nullable=True)

    # JSON payloads for tags, multilingual content and extra metadata
    tags = Column(JSON, nullable=True)  # JSON array of tags
    language_response = Column(JSON, nullable=True)  # {"english": "", "tamil": ""}
    response_metadata = Column(JSON, nullable=True)

    # Use timezone-aware timestamp for safer production usage
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_activity_at = Column(TIMESTAMP, server_default=func.now())
    query_count = Column(Integer, default=0, nullable=False)


# ============================================================================
# UNIFIED RAG MODELS (Current Source of Truth)
# ============================================================================

class DocsChunk(Base):
    """Chunks from general documents (PDF, CSV, etc.)."""
    __tablename__ = "docs_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(384))  # Dimension should match EXPECTED_EMBEDDING_DIM
    fts_vector = Column(Text, info={"skip_autogenerate": True}) # Handled by PostgreSQL FTS
    chunk_metadata = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    chunk_hash = Column(String(64), index=True, nullable=True)  # SHA-256 hash for deduplication
    file_hash = Column(String(200), nullable=True)
    domain = Column(String(100))
    sub_domain = Column(String(100))
    source_file = Column(String(1000))
    chunk_index = Column(Integer)


class BookChunk(Base):
    """Chunks from archival books."""
    __tablename__ = "book_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(384))
    fts_vector = Column(Text, info={"skip_autogenerate": True})
    chunk_metadata = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    chunk_hash = Column(String(64), index=True, nullable=True)
    file_hash = Column(String(200), nullable=True)
    source_file = Column(String(1000))
    chunk_index = Column(Integer) # Renamed from chunk_number for unification
