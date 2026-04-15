# DB Service

## Overview

The **DB Service** provides centralized database access, ORM models, and data persistence for the entire LLM User Service. It manages PostgreSQL connections, SQLAlchemy models, CRUD operations, and database migrations.

## Purpose

- Database connection management
- SQLAlchemy ORM models
- CRUD operations
- Database migrations
- Connection pooling
- Transaction management

## Architecture

```
db_service/
├── __init__.py
├── database.py         # Connection setup, session management
├── models.py           # SQLAlchemy ORM models
├── crud.py             # CRUD operations
└── migrations/         # Database migrations
    ├── __init__.py
    ├── add_indexes.py
    ├── fix_document_chunks.py
    └── tables_migration.py
```

## Key Components

### 1. Database Connection (`database.py`)

```python
# Database URL from environment
DATABASE_URL = settings.DATABASE_URL

# SQLAlchemy engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,  # Default: 5
    max_overflow=settings.DB_MAX_OVERFLOW,  # Default: 10
    pool_pre_ping=settings.DB_POOL_PRE_PING  # Default: True
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 2. ORM Models (`models.py`)

All database tables are defined as SQLAlchemy models:

#### UserQuery
```python
class UserQuery(Base):
    __tablename__ = "user_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    session_id = Column(String, index=True)
    language = Column(String)
    user_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### QueryResponse
```python
class QueryResponse(Base):
    __tablename__ = "query_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey("user_queries.id"))
    response_text = Column(Text)
    retrieved_context_ids = Column(ARRAY(Integer))
    llm_model = Column(String)
    response_metadata = Column(JSONB)
    latency_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### DocumentChunk
```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(384))  # pgvector
    source_name = Column(String, index=True)
    file_path = Column(String)
    chunk_index = Column(Integer)
    metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### ChatSession
```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    session_id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    is_temporary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### ChatMessage
```python
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.session_id"))
    query_id = Column(Integer, ForeignKey("user_queries.id"))
    response_id = Column(Integer, ForeignKey("query_responses.id"))
    is_favourite = Column(Boolean, default=False)
    tags = Column(ARRAY(String))
    feedback = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 3. CRUD Operations (`crud.py`)

Common database operations:

```python
# Create
def create_user_query(db: Session, query_data: dict) -> models.UserQuery:
    query = models.UserQuery(**query_data)
    db.add(query)
    db.commit()
    db.refresh(query)
    return query

# Read
def get_user_query(db: Session, query_id: int) -> models.UserQuery:
    return db.query(models.UserQuery).filter(
        models.UserQuery.id == query_id
    ).first()

# Update
def update_user_query(db: Session, query_id: int, updates: dict):
    db.query(models.UserQuery).filter(
        models.UserQuery.id == query_id
    ).update(updates)
    db.commit()

# Delete
def delete_user_query(db: Session, query_id: int):
    db.query(models.UserQuery).filter(
        models.UserQuery.id == query_id
    ).delete()
    db.commit()
```

### 4. Migrations (`migrations/`)

Database schema migrations:

#### tables_migration.py
Creates core tables (chat_sessions, chat_messages, subscriptions, file_uploads)

#### add_indexes.py
Adds performance indexes on frequently queried columns

#### fix_document_chunks.py
Fixes document_chunks table schema issues

## Database Schema

### Core Tables

```mermaid
erDiagram
    USER_QUERIES ||--|| QUERY_RESPONSES : generates
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : contains
    CHAT_MESSAGES }|--|| USER_QUERIES : references
    CHAT_MESSAGES }|--|| QUERY_RESPONSES : references
    QUERY_RESPONSES ||--o{ DOCUMENT_CHUNKS : uses
    
    USER_QUERIES {
        int id PK
        text query_text
        string session_id
        string language
        string user_id
        datetime created_at
    }
    
    QUERY_RESPONSES {
        int id PK
        int query_id FK
        text response_text
        array retrieved_context_ids
        string llm_model
        jsonb response_metadata
        float latency_ms
        datetime created_at
    }
    
    DOCUMENT_CHUNKS {
        int id PK
        text chunk_text
        vector embedding
        string source_name
        string file_path
        int chunk_index
        jsonb metadata
        datetime created_at
    }
    
    CHAT_SESSIONS {
        string session_id PK
        string user_id
        boolean is_temporary
        datetime created_at
        datetime updated_at
    }
    
    CHAT_MESSAGES {
        int id PK
        string session_id FK
        int query_id FK
        int response_id FK
        boolean is_favourite
        array tags
        string feedback
        datetime created_at
    }
```

## Configuration

### Environment Variables

```python
# Database Connection
DATABASE_URL: str = "postgresql://user:pass@localhost:5432/dbname"

# Connection Pool
DB_POOL_SIZE: int = 5
DB_MAX_OVERFLOW: int = 10
DB_POOL_PRE_PING: bool = True
```

### Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]
```

Example:
```
postgresql://postgres:password@localhost:5432/llm_service
```

## Usage Examples

### Get Database Session

```python
from src.db_service.database import get_db
from fastapi import Depends

@app.get("/example")
def example_endpoint(db: Session = Depends(get_db)):
    # Use db session
    queries = db.query(models.UserQuery).all()
    return {"queries": queries}
```

### Create Record

```python
from src.db_service import crud, models

# Create user query
query_data = {
    "query_text": "What is RAG?",
    "session_id": "13022026-abc123",
    "user_id": "user_123"
}
query = crud.create_user_query(db, query_data)
```

### Query with Filters

```python
# Get recent queries
recent_queries = db.query(models.UserQuery)\
    .filter(models.UserQuery.created_at >= cutoff_time)\
    .order_by(models.UserQuery.created_at.desc())\
    .limit(100)\
    .all()

# Get queries by session
session_queries = db.query(models.UserQuery)\
    .filter(models.UserQuery.session_id == session_id)\
    .all()
```

### Join Queries

```python
# Get queries with responses
results = db.query(
    models.UserQuery,
    models.QueryResponse
).join(
    models.QueryResponse,
    models.UserQuery.id == models.QueryResponse.query_id
).all()
```

### Vector Search

```python
from sqlalchemy import text

# pgvector similarity search
query_embedding = [0.1, 0.2, ...]  # 384-dim vector

results = db.execute(
    text("""
        SELECT id, chunk_text, source_name,
               embedding <=> :query_embedding AS distance
        FROM document_chunks
        ORDER BY embedding <=> :query_embedding
        LIMIT :limit
    """),
    {
        "query_embedding": query_embedding,
        "limit": 5
    }
).fetchall()
```

## Migrations

### Running Migrations

```python
from src.db_service.migrations.tables_migration import run_tables_migration
from src.db_service.database import engine

# Run table migrations
run_tables_migration(engine)
```

### Creating New Migration

1. Create new file in `migrations/`
2. Define migration function
3. Import and run in startup

Example:
```python
# migrations/add_new_column.py
from sqlalchemy import text

def run_migration(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE user_queries
            ADD COLUMN IF NOT EXISTS new_column VARCHAR(255)
        """))
        conn.commit()
```

## Performance Optimization

### Indexes

```sql
-- Frequently queried columns
CREATE INDEX idx_user_queries_session_id ON user_queries(session_id);
CREATE INDEX idx_user_queries_user_id ON user_queries(user_id);
CREATE INDEX idx_user_queries_created_at ON user_queries(created_at);

-- Vector index (HNSW for fast approximate search)
CREATE INDEX idx_document_chunks_embedding ON document_chunks
USING hnsw (embedding vector_cosine_ops);
```

### Connection Pooling

```python
# Optimal pool settings for production
DB_POOL_SIZE = 10  # Base connections
DB_MAX_OVERFLOW = 20  # Additional connections under load
DB_POOL_PRE_PING = True  # Verify connections before use
```

### Query Optimization

```python
# Use select_related to avoid N+1 queries
from sqlalchemy.orm import joinedload

queries = db.query(models.UserQuery)\
    .options(joinedload(models.UserQuery.response))\
    .all()

# Use pagination for large result sets
queries = db.query(models.UserQuery)\
    .offset(offset)\
    .limit(limit)\
    .all()
```

## Monitoring

### Connection Pool Metrics

```python
# Check pool status
pool = engine.pool
print(f"Pool size: {pool.size()}")
print(f"Checked out: {pool.checkedout()}")
print(f"Overflow: {pool.overflow()}")
```

### Query Performance

```python
import time

start = time.time()
result = db.query(models.UserQuery).all()
duration = time.time() - start

logger.info(f"Query took {duration:.3f}s")
```

## Error Handling

### Common Errors

#### Connection Error
```python
from sqlalchemy.exc import OperationalError

try:
    db.query(models.UserQuery).all()
except OperationalError as e:
    logger.error(f"Database connection failed: {e}")
```

#### Integrity Error
```python
from sqlalchemy.exc import IntegrityError

try:
    db.add(new_record)
    db.commit()
except IntegrityError as e:
    db.rollback()
    logger.error(f"Integrity constraint violated: {e}")
```

## Testing

### Unit Tests

```python
import pytest
from src.db_service import models, crud

def test_create_user_query(db_session):
    query_data = {
        "query_text": "Test query",
        "session_id": "test-session"
    }
    query = crud.create_user_query(db_session, query_data)
    assert query.id is not None
    assert query.query_text == "Test query"
```

### Test Database Setup

```python
@pytest.fixture
def db_session():
    # Create test database
    engine = create_engine("postgresql://test:test@localhost/test_db")
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)
```

## Security

### SQL Injection Prevention
- **Use ORM** - SQLAlchemy prevents SQL injection
- **Parameterized Queries** - Never concatenate user input
- **Input Validation** - Validate all inputs with Pydantic

### Connection Security
- **SSL/TLS** - Use encrypted connections in production
- **Credentials** - Store in environment variables, not code
- **Least Privilege** - Database user should have minimal permissions

## Future Enhancements

- [ ] Read replicas for scaling reads
- [ ] Database sharding for horizontal scaling
- [ ] Automated backup and restore
- [ ] Query result caching (Redis)
- [ ] Database monitoring dashboard
- [ ] Automated migration rollback
- [ ] Multi-tenancy support
- [ ] Audit logging

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md)
- [All Services](../../docs/ARCHITECTURE.md#service-components)

---

**Service Version**: 1.0  
**Last Updated**: February 2026
