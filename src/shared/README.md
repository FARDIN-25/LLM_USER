# Shared Module

## Overview

The **Shared Module** provides common utilities, configurations, schemas, and cross-cutting concerns used across all service modules in the LLM User Service.

## Purpose

- Centralized configuration management
- Shared data models (Pydantic schemas)
- Common exception handling
- Logging setup and utilities
- Monitoring and metrics
- Shared constants and enums

## Architecture

```
shared/
├── config.py           # Configuration and settings
├── schemas.py          # Pydantic data models
├── exceptions.py       # Custom exceptions
├── logging.py          # Logging configuration
├── monitoring.py       # Metrics and monitoring
├── constants.py        # Shared constants
└── templates/          # Jinja2 templates
    ├── index.html
    ├── history.html
    └── monitor.html
```

## Components

### 1. Configuration (`config.py`)

Centralized configuration using Pydantic Settings:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "LLM RAG Enterprise"
    APP_ENV: str = "development"
    
    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    
    # LLM
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "mistralai/mistral-7b-instruct"
    
    # Feature Flags
    ENABLE_HYBRID_SEARCH: bool = True
    ENABLE_RERANKING: bool = True
    ENABLE_QUERY_EXPANSION: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

### 2. Schemas (`schemas.py`)

Shared Pydantic models for request/response validation:

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class QueryCreate(BaseModel):
    query_text: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    language: Optional[str] = None
    is_temporary: bool = False

class QueryResponse(BaseModel):
    id: int
    query_text: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatSessionCreate(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    is_temporary: bool = False

class ChatMessageCreate(BaseModel):
    session_id: str
    query_id: int
    response_id: int
    react: bool = False
    tags: List[str] = []
    feedback: Optional[str] = None
```

### 3. Exceptions (`exceptions.py`)

Custom exception hierarchy:

```python
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

class BaseAppException(Exception):
    """Base exception for application errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class DatabaseError(BaseAppException):
    """Database operation failed."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500)

class ValidationError(BaseAppException):
    """Input validation failed."""
    def __init__(self, message: str):
        super().__init__(message, status_code=422)

class AuthenticationError(BaseAppException):
    """Authentication failed."""
    def __init__(self, message: str):
        super().__init__(message, status_code=401)

class NotFoundError(BaseAppException):
    """Resource not found."""
    def __init__(self, message: str):
        super().__init__(message, status_code=404)

# Exception handlers
async def app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )

async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
```

### 4. Logging (`logging.py`)

Structured logging configuration:

```python
import logging
import sys
from typing import Optional

def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """
    Configure application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger

# Application logger
logger = logging.getLogger("fintax")
```

### 5. Monitoring (`monitoring.py`)

Metrics collection and monitoring:

```python
from typing import Dict, List
from datetime import datetime

class Monitoring:
    """Simple in-memory monitoring."""
    
    def __init__(self):
        self.metrics: Dict[str, List] = {
            "requests": [],
            "errors": [],
            "latencies": []
        }
    
    def record_request(self, endpoint: str, latency: float):
        """Record API request."""
        self.metrics["requests"].append({
            "endpoint": endpoint,
            "latency": latency,
            "timestamp": datetime.utcnow()
        })
    
    def record_error(self, error: str, context: dict = None):
        """Record error."""
        self.metrics["errors"].append({
            "error": error,
            "context": context or {},
            "timestamp": datetime.utcnow()
        })
    
    def get_summary(self) -> dict:
        """Get metrics summary."""
        return {
            "total_requests": len(self.metrics["requests"]),
            "total_errors": len(self.metrics["errors"]),
            "avg_latency": self._calculate_avg_latency()
        }
    
    def _calculate_avg_latency(self) -> float:
        if not self.metrics["latencies"]:
            return 0.0
        return sum(self.metrics["latencies"]) / len(self.metrics["latencies"])

# Global monitoring instance
monitoring = Monitoring()
```

## Usage Examples

### Configuration

```python
from src.shared.config import settings

# Access configuration
database_url = settings.DATABASE_URL
llm_model = settings.OPENROUTER_MODEL

# Check feature flags
if settings.ENABLE_HYBRID_SEARCH:
    # Use hybrid search
    pass
```

### Schemas

```python
from src.shared.schemas import QueryCreate

# Validate request data
query_data = {
    "query_text": "What is RAG?",
    "session_id": "13022026-abc123"
}

query = QueryCreate(**query_data)
print(query.query_text)  # "What is RAG?"
```

### Exceptions

```python
from src.shared.exceptions import NotFoundError, DatabaseError

# Raise custom exception
def get_user(user_id: str):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    return user

# Handle database errors
try:
    result = db.execute(query)
except Exception as e:
    raise DatabaseError(f"Query failed: {e}")
```

### Logging

```python
from src.shared.logging import logger

# Log messages
logger.info("Processing query")
logger.warning("Cache miss")
logger.error("Database connection failed", exc_info=True)
logger.debug(f"Query embedding: {embedding[:5]}...")
```

### Monitoring

```python
from src.shared.monitoring import monitoring

# Record request
monitoring.record_request("/api/chat", latency=1.5)

# Record error
monitoring.record_error(
    "LLM API timeout",
    context={"model": "mistral-7b", "timeout": 20}
)

# Get summary
summary = monitoring.get_summary()
print(f"Total requests: {summary['total_requests']}")
```

## Templates

### Web UI Templates

The shared module includes Jinja2 templates for the web interface:

- **index.html** - Main dashboard
- **history.html** - Query history page
- **monitor.html** - Performance monitoring dashboard

Templates use:
- Bootstrap 5 for styling
- Chart.js for visualizations
- Vanilla JavaScript for interactivity

## Constants

Common constants and enums:

```python
# constants.py

# Query expansion strategies
EXPANSION_STRATEGIES = [
    "static",
    "llm",
    "hybrid",
    "module_wise",
    "token_optimized"
]

# Reranker types
RERANKER_TYPES = [
    "cross-encoder",
    "cohere",
    "bge",
    "llm"
]

# Supported file types
SUPPORTED_FILE_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown"
}

# Default values
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_TOP_K = 5
```

## Testing

### Unit Tests

```bash
pytest tests/shared/test_config.py
pytest tests/shared/test_schemas.py
pytest tests/shared/test_exceptions.py
```

## Future Enhancements

- [ ] Advanced metrics (Prometheus integration)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Configuration validation
- [ ] Schema versioning
- [ ] Custom logging formatters (JSON)
- [ ] Rate limiting utilities
- [ ] Caching utilities (Redis)

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md)
- [All Services](../../docs/ARCHITECTURE.md#service-components)

---

**Module Version**: 1.0  
**Last Updated**: February 2026
