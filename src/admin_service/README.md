# Admin Service

## Overview

The **Admin Service** provides system administration, monitoring, and management capabilities for the LLM User Service. It handles health checks, diagnostics, session management, and system metrics.

## Purpose

- System health monitoring
- Performance diagnostics
- Session tracking and management
- Resource information
- Response logging
- Endpoint status monitoring

## Architecture

```
admin_service/
└── api/
    └── routes.py    # FastAPI routes for admin endpoints
```

The Admin Service follows a simplified architecture with direct route implementations, as it primarily provides read-only system information and doesn't require complex business logic layers.

## Key Features

### 1. Health Monitoring
- **System Health Check** - Database connectivity, service availability
- **Component Status** - LLM, vector store, query expansion, reranking
- **Resource Monitoring** - Memory usage, storage status

### 2. Diagnostics
- **Detailed System Info** - Configuration, feature flags, model status
- **Performance Metrics** - Request counts, latency, token usage
- **Error Tracking** - Recent errors and warnings

### 3. Session Management
- **Session Tracking** - Active sessions, user activity
- **Session Listing** - All sessions with metadata
- **Session Analytics** - Query counts, timestamps

### 4. Response Logging
- **Query History** - Recent queries and responses
- **Memory Retrieval** - Persisted conversation history
- **Performance Logs** - Latency and token metrics

## API Endpoints

### Health & Status

#### `GET /api/health`
System health check with detailed component status.

**Response**:
```json
{
  "status": "healthy",
  "app_name": "LLM RAG Enterprise",
  "app_version": "0.2.0",
  "vectorstore_initialized": true,
  "langchain_available": true,
  "query_expansion_available": true,
  "reranking_available": true,
  "hybrid_retrieval_available": true,
  "database_connected": true,
  "llm_configured": true,
  "llm_available": true,
  "llm_model": "mistralai/mistral-7b-instruct",
  "llm_status": "Available"
}
```

#### `GET /api/diagnostics`
Detailed diagnostics information.

**Response**:
```json
{
  "status": "healthy",
  "database": {
    "connected": true,
    "url": "postgresql://..."
  },
  "llm": {
    "available": true,
    "model": "mistralai/mistral-8b",
    "provider": "MISTRAL"
  },
  "features": {
    "query_expansion": true,
    "reranking": true,
    "hybrid_search": true
  }
}
```

### Monitoring

#### `GET /api/monitoring/metrics`
Get all monitoring metrics.

**Response**:
```json
{
  "requests_total": 1234,
  "average_latency": 1.5,
  "token_totals": {
    "prompt": 50000,
    "completion": 25000
  },
  "cache_summary": {
    "size": 100,
    "hits": 500,
    "misses": 734
  }
}
```

#### `GET /api/metrics/performance`
Performance metrics from database.

**Response**:
```json
{
  "requests_total": 1234,
  "average_latency": 1.5,
  "accuracy_estimate": 0.85,
  "token_totals": {
    "prompt": 50000,
    "completion": 25000
  },
  "requests_with_context": 1050
}
```

### Session Management

#### `GET /api/sessions`
List all sessions ordered by last activity.

**Response**:
```json
{
  "sessions": [
    {
      "session_id": "13022026-abc123",
      "user_id": "user_123",
      "is_temporary": false,
      "created_at": "2026-02-13T10:00:00Z",
      "updated_at": "2026-02-13T11:00:00Z"
    }
  ]
}
```

#### `GET /api/sessions/info`
Get session information with query counts.

**Response**:
```json
{
  "total_sessions": 50,
  "active_sessions": 10,
  "sessions": [
    {
      "session_id": "13022026-abc123",
      "query_count": 15,
      "last_activity": "2026-02-13T11:00:00Z"
    }
  ]
}
```

#### `POST /api/sessions/track`
Track a session and update its activity.

**Request**:
```json
{
  "session_id": "13022026-abc123",
  "user_id": "user_123",
  "is_temporary": false
}
```

### Resource Information

#### `GET /api/resources`
Get information about knowledge base resources.

**Response**:
```json
{
  "total_chunks": 5000,
  "total_documents": 50,
  "sources": [
    {
      "source_name": "document1.pdf",
      "chunk_count": 100
    }
  ]
}
```

### Response Logging

#### `GET /api/response-log`
Get recent query responses from database.

**Query Parameters**:
- `limit` (int, default: 20) - Number of responses to retrieve

**Response**:
```json
{
  "responses": [
    {
      "id": 1,
      "query_text": "What is RAG?",
      "response_text": "RAG stands for...",
      "latency_ms": 1500,
      "created_at": "2026-02-13T10:00:00Z"
    }
  ]
}
```

#### `GET /api/memory`
Get memory (queries and answers) from database.

**Response**:
```json
{
  "memory": [
    {
      "question": "What is RAG?",
      "answer": "RAG stands for...",
      "timestamp": "2026-02-13T10:00:00Z"
    }
  ]
}
```

### Endpoint Status

#### `GET /api/endpoints/status`
Get status of all API endpoints across services.

**Response**:
```json
{
  "user_service": {
    "status": "healthy",
    "endpoints": [
      {
        "path": "/api/health",
        "status": "ok",
        "response_time": 50
      }
    ]
  },
  "cleaning_service": {
    "status": "unavailable"
  },
  "ingestion_service": {
    "status": "healthy"
  }
}
```

### Chat Session Management

#### `POST /api/chat-sessions`
Create a new chat session.

**Request**:
```json
{
  "session_id": "13022026-abc123",
  "user_id": "user_123",
  "is_temporary": false
}
```

#### `GET /api/chat-sessions/{session_id}`
Get a chat session by ID.

#### `GET /api/chat-sessions`
List chat sessions for a user.

**Query Parameters**:
- `user_id` (string, required) - User ID
- `limit` (int, default: 100) - Max sessions to return

#### `PATCH /api/chat-sessions/{session_id}`
Update a chat session.

**Request**:
```json
{
  "is_temporary": true
}
```

#### `DELETE /api/chat-sessions/{session_id}`
Delete a chat session and its messages.

### Chat Message Management

#### `POST /api/chat-messages`
Create a chat message linking a query and response.

**Request**:
```json
{
  "session_id": "13022026-abc123",
  "query_id": 1,
  "response_id": 1,
  "is_favourite": false,
  "tags": ["important"],
  "feedback": "helpful"
}
```

#### `GET /api/chat-messages/{message_id}`
Get a chat message by ID.

#### `GET /api/chat-messages`
List messages in a session.

**Query Parameters**:
- `session_id` (string, required) - Session ID
- `favourites_only` (bool, default: false) - Only favourites
- `limit` (int, default: 100) - Max messages

#### `PATCH /api/chat-messages/{message_id}`
Update message (favourite, tags, feedback).

#### `DELETE /api/chat-messages/{message_id}`
Delete a chat message.

### Subscription Management

#### `POST /api/subscriptions`
Create a subscription for a user.

**Request**:
```json
{
  "user_id": "user_123",
  "plan_type": "premium",
  "start_date": "2026-02-13",
  "end_date": "2027-02-13"
}
```

#### `GET /api/subscriptions/{user_id}`
Get subscription for a user.

#### `PATCH /api/subscriptions/{user_id}`
Update subscription.

#### `DELETE /api/subscriptions/{user_id}`
Delete subscription.

### File Upload Management

#### `POST /api/file-uploads`
Create a file upload record.

**Request**:
```json
{
  "user_id": "user_123",
  "filename": "document.pdf",
  "file_path": "/uploads/document.pdf"
}
```

#### `GET /api/file-uploads/{upload_id}`
Get file upload by ID.

#### `GET /api/file-uploads`
List file uploads for a user.

**Query Parameters**:
- `user_id` (string, required) - User ID
- `limit` (int, default: 100) - Max uploads

#### `PATCH /api/file-uploads/{upload_id}`
Update file upload status.

#### `DELETE /api/file-uploads/{upload_id}`
Delete file upload record.

## Dependencies

### Internal Dependencies
- `src.db_service` - Database access and models
- `src.shared` - Shared schemas, config, monitoring

### External Dependencies
- `fastapi` - Web framework
- `sqlalchemy` - Database ORM
- `requests` - HTTP client for external service checks

## Configuration

The Admin Service uses settings from `src.shared.config`:

```python
# No specific admin service configuration
# Uses global settings for database, logging, etc.
```

## Usage Examples

### Check System Health

```python
import requests

response = requests.get("http://localhost:8000/api/health")
health = response.json()

if health["status"] == "healthy":
    print("System is healthy")
    print(f"LLM: {health['llm_model']}")
    print(f"Database: {'Connected' if health['database_connected'] else 'Disconnected'}")
```

### Get Performance Metrics

```python
response = requests.get("http://localhost:8000/api/metrics/performance")
metrics = response.json()

print(f"Total Requests: {metrics['requests_total']}")
print(f"Average Latency: {metrics['average_latency']}s")
print(f"Accuracy: {metrics['accuracy_estimate'] * 100}%")
```

### Track Session

```python
session_data = {
    "session_id": "13022026-abc123",
    "user_id": "user_123",
    "is_temporary": False
}

response = requests.post(
    "http://localhost:8000/api/sessions/track",
    json=session_data
)
```

## Monitoring

### Key Metrics
- **System Health** - Overall system status
- **Component Availability** - LLM, database, vector store
- **Request Metrics** - Count, latency, errors
- **Resource Usage** - Memory, storage, connections

### Health Check Intervals
- **Production**: Every 30 seconds
- **Development**: Every 60 seconds

## Error Handling

The Admin Service uses standard FastAPI exception handling:

```python
from fastapi import HTTPException

# Example error response
{
  "detail": "Database connection failed"
}
```

### Common Errors
- `500 Internal Server Error` - Database connection issues
- `503 Service Unavailable` - External service unavailable
- `404 Not Found` - Session or resource not found

## Testing

### Unit Tests
```bash
pytest tests/admin_service/
```

### Integration Tests
```bash
pytest tests/integration/test_admin_endpoints.py
```

### Health Check Test
```bash
curl http://localhost:8000/api/health
```

## Performance Considerations

### Optimization Strategies
- **Caching** - Cache health check results (30s TTL)
- **Connection Pooling** - Reuse database connections
- **Async Operations** - Non-blocking I/O for external checks

### Scalability
- **Stateless Design** - No session state in service
- **Read-Heavy** - Optimized for read operations
- **Lightweight** - Minimal resource usage

## Security

### Access Control
- **Public Endpoints** - `/health` (no auth required)
- **Protected Endpoints** - All admin endpoints (JWT required)

### Rate Limiting
- Recommended: 100 requests/minute per IP

## Future Enhancements

- [ ] Real-time metrics dashboard
- [ ] Advanced analytics and reporting
- [ ] Alerting and notifications
- [ ] Custom metric definitions
- [ ] Historical trend analysis
- [ ] Export metrics to external monitoring tools

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md)
- [API Documentation](../../docs/api_documentation.md)
- [Database Service](../db_service/README.md)
- [Shared Module](../shared/README.md)

---

**Service Version**: 1.0  
**Last Updated**: February 2026
