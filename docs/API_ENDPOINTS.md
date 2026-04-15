# API Endpoints — LLM User Service

> **Canonical reference** — one path per endpoint.  
> Base URL: `http://localhost:8001` (or configured host).  
> Last updated: 2026-03-03

---

## Summary

| Category              | Prefix        | Endpoints |
|-----------------------|---------------|-----------|
| App (root / main)     | `/`, `/api`   | 10        |
| Auth                  | `/api/auth`   | 4         |
| User (chat, admin)    | `/api/user`   | 45+       |
| Ingestion             | `/api/user`   | 2         |
| Retrieval (optional)  | `/api/retrieval` | 1     |

---

## 1. App-level (main.py)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/` | Dashboard UI (index.html) | Cookie |
| GET | `/chat` | Dashboard UI (same as `/`) | Cookie |
| GET | `/health` | Health (DB, vectorstore, LLM, reranker) | — |
| GET | `/.well-known/appspecific/com.chrome.devtools.json` | Chrome DevTools manifest | — |
| GET | `/history` | History page HTML | Cookie |
| GET | `/monitor` | Monitor dashboard HTML | — |
| GET | `/api/history` | Query history (7 days, KB/LLM stats) | — |
| GET | `/api/user/history` | Alias for `/api/history` | — |
| GET | `/api/metrics/performance` | Performance metrics (latency, tokens) | — |

---

## 2. Auth — `/api/auth`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/auth/register` | Registration page | — |
| POST | `/api/auth/register` | Register user | — |
| GET | `/api/auth/login` | Login page | — |
| POST | `/api/auth/login` | Login (JWT + cookie) | — |

---

## 3. Chat — `/api/user`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/user/chat` | RAG chat (KB + LLM) | Required |
| POST | `/api/user/chat/new` | Create new chat session | Required |
| POST | `/api/user/query` | RAG pipeline (typed schema) | — |
| POST | `/api/user/chat/edit` | Edit question & regenerate answer | Required |
| POST | `/api/user/chat/regenerate` | Regenerate answer | Required |
| POST | `/api/user/chat/react` | Set emoji reaction on message | Required |
| GET | `/api/user/chat/react/{message_id}` | Get reaction for message | Required |
| GET | `/api/user/favourites` | Favourite messages (current user) | Required |
| GET | `/api/user/sessions/history` | Session list for sidebar | Required |
| PATCH | `/api/user/sessions/{session_id}/history` | Rename session title | Required |
| GET | `/api/user/sessions/{session_id}/messages` | Conversation for session | Required |
| GET | `/api/user/sessions/{session_id}/favourites` | Favourites for session | Required |

---

## 4. Admin / System — `/api/user`

### System & health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/user/info` | API info (service name, status) |
| GET | `/api/user/health` | Health (DB, reranker, query expansion, LLM) |
| GET | `/api/user/diagnostics` | System diagnostics |
| GET | `/api/user/storage-status` | Storage usage (placeholder) |
| GET | `/api/user/upload-limits` | Upload limits for UI |
| GET | `/api/user/endpoints-status` | Status of all endpoints |

### Monitoring

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/user/monitoring/metrics` | Monitoring metrics |
| GET | `/api/user/monitoring/memory` | Queries/answers (last 24h) |
| GET | `/api/user/monitoring/resources` | KB resources (chunks, files) |
| POST | `/api/user/monitoring/rag-settings` | Update RAG settings |
| POST | `/api/user/monitoring/model-settings` | Update model settings |
| GET | `/api/user/monitoring/response-log` | Recent responses (24h) |
| GET | `/api/user/monitoring/sessions` | Session info with query counts |

### Legacy session

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/user/session/track` | Track session activity |
| GET | `/api/user/session/list` | List all sessions |

### Chat sessions CRUD

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/user/sessions` | Create chat session |
| GET | `/api/user/sessions/{session_id}` | Get session |
| GET | `/api/user/sessions` | List sessions by user_id |
| PATCH | `/api/user/sessions/{session_id}` | Update session |
| PATCH | `/api/user/sessions` | Update session (ID in body) |
| DELETE | `/api/user/sessions/{session_id}` | Delete session (cascade) |

### Messages CRUD

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/user/messages` | Create chat message |
| GET | `/api/user/messages/{message_id}` | Get message |
| GET | `/api/user/messages` | List messages by session |
| PATCH | `/api/user/messages/{message_id}` | Update message (react, tags, feedback) |
| DELETE | `/api/user/messages/{message_id}` | Delete message |

### Subscriptions CRUD

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/user/subscriptions` | Create subscription |
| GET | `/api/user/subscriptions/{user_id}` | Get subscription |
| PATCH | `/api/user/subscriptions/{user_id}` | Update subscription |
| DELETE | `/api/user/subscriptions/{user_id}` | Delete subscription |

### File uploads CRUD

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/user/files` | Record file upload |
| GET | `/api/user/files/{file_id}` | Get file upload |
| GET | `/api/user/files` | List file uploads by user |
| PATCH | `/api/user/files/{file_id}` | Update file upload |
| DELETE | `/api/user/files/{file_id}` | Delete file upload record |

### Placeholders

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/user/subscription/plans` | Subscription plans (static) |
| GET | `/api/user/privacy/info` | Privacy info (static) |

---

## 5. Ingestion — `/api/user`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/user/upload` | Upload file (folder, tags) | Required |
| POST | `/api/user/upload/metadata` | Record upload metadata | Required |

---

## 6. User profile — `/api/user`

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/user/me` | Current user profile | Stub (TODO) |
| PUT | `/api/user/me` | Update current user | Stub (TODO) |

---

## 7. Retrieval (optional) — `/api/retrieval`

When hybrid retrieval router is included:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/retrieval/search` | Hybrid retrieval search |

---

## Notes

- **Auth:** Use cookie `access_token` or `Authorization: Bearer <token>` where required.
- **History:** Use `/api/history` or `/api/user/history`; same handler.
- **Stub endpoints:** `/api/user/me` (GET/PUT) are not implemented; return null until implemented.
