# User Service

## Overview

The **User Service** manages user profiles, preferences, and user-related operations for the LLM User Service. It provides CRUD operations for user data and integrates with the authentication system.

## Purpose

- User profile management
- User preferences and settings
- User data CRUD operations
- User activity tracking
- Integration with auth service

## Architecture

```
user_service/
├── api/
│   └── routes.py       # User management endpoints
├── application/
│   └── (services)      # User business logic
├── domain/
│   └── (entities)      # User domain models
└── infrastructure/
    └── (adapters)      # External integrations
```

## Key Features

### 1. Profile Management
- **Create Profile** - New user profile creation
- **Read Profile** - Get user profile data
- **Update Profile** - Modify user information
- **Delete Profile** - Remove user account

### 2. Preferences
- **User Settings** - Application preferences
- **Notification Settings** - Communication preferences
- **Display Preferences** - UI customization

### 3. Activity Tracking
- **Query History** - Track user queries
- **Session History** - Track user sessions
- **Usage Statistics** - User activity metrics

## API Endpoints

### User Profile

#### `GET /api/user/profile`
Get current user profile.

**Headers**:
```
Authorization: Bearer <token>
```

**Response**:
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "full_name": "John Doe",
  "avatar_url": "https://example.com/avatar.jpg",
  "created_at": "2026-02-13T10:00:00Z",
  "updated_at": "2026-02-13T11:00:00Z"
}
```

#### `PUT /api/user/profile`
Update user profile.

**Headers**:
```
Authorization: Bearer <token>
```

**Request**:
```json
{
  "full_name": "John Smith",
  "avatar_url": "https://example.com/new-avatar.jpg"
}
```

**Response**:
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "full_name": "John Smith",
  "avatar_url": "https://example.com/new-avatar.jpg",
  "updated_at": "2026-02-13T12:00:00Z"
}
```

#### `DELETE /api/user/profile`
Delete user account.

**Headers**:
```
Authorization: Bearer <token>
```

**Response**:
```json
{
  "message": "Account deleted successfully"
}
```

### User Preferences

#### `GET /api/user/preferences`
Get user preferences.

**Response**:
```json
{
  "theme": "dark",
  "language": "en",
  "notifications_enabled": true,
  "email_notifications": false,
  "query_expansion_default": true,
  "reranking_default": true
}
```

#### `PUT /api/user/preferences`
Update user preferences.

**Request**:
```json
{
  "theme": "light",
  "notifications_enabled": false
}
```

**Response**:
```json
{
  "theme": "light",
  "language": "en",
  "notifications_enabled": false,
  "email_notifications": false
}
```

### User Activity

#### `GET /api/user/activity`
Get user activity summary.

**Response**:
```json
{
  "total_queries": 150,
  "total_sessions": 25,
  "last_active": "2026-02-13T11:00:00Z",
  "favorite_topics": ["AI", "Machine Learning", "RAG"],
  "avg_queries_per_session": 6
}
```

#### `GET /api/user/history`
Get user query history.

**Query Parameters**:
- `limit` (int, default: 20) - Number of queries
- `offset` (int, default: 0) - Pagination offset

**Response**:
```json
{
  "queries": [
    {
      "id": 123,
      "query_text": "What is RAG?",
      "created_at": "2026-02-13T10:00:00Z",
      "session_id": "13022026-abc123"
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0
}
```

## Dependencies

### Internal Dependencies
- `src.db_service` - Database access
- `src.auth_service` - Authentication
- `src.shared` - Configuration, schemas

### External Dependencies
- `fastapi` - Web framework
- `sqlalchemy` - Database ORM
- `pydantic` - Data validation

## Configuration

```python
# User Configuration
DEFAULT_THEME: str = "light"
DEFAULT_LANGUAGE: str = "en"
MAX_QUERY_HISTORY: int = 1000
```

## Usage Examples

### Get User Profile

```python
import requests

headers = {
    "Authorization": f"Bearer {access_token}"
}

response = requests.get(
    "http://localhost:8000/api/user/profile",
    headers=headers
)

profile = response.json()
print(f"User: {profile['full_name']}")
```

### Update Profile

```python
headers = {
    "Authorization": f"Bearer {access_token}"
}

data = {
    "full_name": "John Smith"
}

response = requests.put(
    "http://localhost:8000/api/user/profile",
    headers=headers,
    json=data
)

updated_profile = response.json()
```

### Get User Activity

```python
response = requests.get(
    "http://localhost:8000/api/user/activity",
    headers=headers
)

activity = response.json()
print(f"Total queries: {activity['total_queries']}")
```

## Security

### Authentication Required
All user endpoints require valid JWT token in Authorization header.

### Data Privacy
- Users can only access their own data
- Profile data is encrypted at rest
- Sensitive data is never logged

## Testing

### Unit Tests
```bash
pytest tests/user_service/test_user_service.py
```

### Integration Tests
```bash
pytest tests/integration/test_user_endpoints.py
```

## Future Enhancements

- [ ] User roles and permissions
- [ ] Team/organization support
- [ ] Advanced analytics dashboard
- [ ] Export user data (GDPR compliance)
- [ ] Two-factor authentication
- [ ] Social login integration
- [ ] User badges and achievements

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md)
- [Auth Service](../auth_service/README.md)
- [DB Service](../db_service/README.md)

---

**Service Version**: 1.0  
**Last Updated**: February 2026
