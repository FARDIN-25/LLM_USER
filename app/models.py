from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, JSON, ARRAY
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(384))
    source_name = Column(String(500))
    file_path = Column(String(1000))
    page_number = Column(Integer)
    chunk_index = Column(Integer)
    section = Column(String(200))
    file_type = Column(String(50))
    ingested_at = Column(TIMESTAMP, server_default=func.now())
    chunk_metadata = Column(JSON, name="metadata")


class UserQuery(Base):
    __tablename__ = "user_queries"

    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    user_id = Column(String(100))
    session_id = Column(String(100))
    created_at = Column(TIMESTAMP, server_default=func.now())
    language = Column(String(10))
    query_metadata = Column(JSON)


class QueryResponse(Base):
    __tablename__ = "query_responses"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer)
    response_text = Column(Text, nullable=False)
    retrieved_context_ids = Column(ARRAY(Integer))
    llm_model = Column(String(100))
    latency_ms = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
    response_metadata = Column(JSON)

