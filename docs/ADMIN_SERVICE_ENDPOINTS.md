# Admin Service Endpoints — LLM User Service

> **Canonical reference** — admin/ops endpoints implemented in `src/admin_service/api/routes.py`.  
> Mounted in `src/main.py` with prefix **`/api/user`**.  
> Base URL: `http://localhost:8001` (or configured host).  
> Last updated: 2026-03-06

---

## Summary

The **Admin Service** provides operational APIs for:

- Health checks and diagnostics (DB/LLM/reranker/query expansion state)
- Monitoring (metrics, response logs, “memory” history, KB resource counts)
- Session tracking/visibility
- Cross-service endpoint status checks (User + Cleaning + Ingestion)
- Admin CRUD for persisted entities (chat sessions/messages, subscriptions, file-upload metadata)

All endpoints below are served under the same prefix: **`/api/user`**.

---

## 1. System & Health — `/api/user`

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| GET | `/api/user/info` | Basic identity (“service running”) metadata. | Smoke checks, dashboard header, simple “is it up” verification. |
| GET | `/api/user/health` | Lightweight health status derived from `app.state` flags (DB connected, features available, LLM key configured). | Load balancers, uptime monitors, quick degraded/healthy determination. |
| GET | `/api/user/diagnostics` | Deeper diagnostics: OS/Python info, component status (DB/reranker/query expansion/LLM model), cache summary (if present). | Debugging configuration problems, dependency failures, cache visibility. |
| GET | `/api/user/storage-status` | Storage/quota status (currently placeholder values in code). | UI/admin tiles for storage usage; future alerting. |
| GET | `/api/user/upload-limits` | Upload constraints for UI (file count, size, extensions). | Frontend validation + consistent server/client upload rules. |

---

## 2. Monitoring — `/api/user/monitoring/*`

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| GET | `/api/user/monitoring/metrics` | Returns in-memory monitoring metrics (`monitoring.get_metrics()`). | Admin dashboards/graphs; quick view of request volume, latency, tokens, cache (depending on what monitoring tracks). |
| GET | `/api/user/monitoring/memory` | Returns recent query+response pairs from DB (last 24h, capped). Falls back to in-memory on DB errors. | Support/debug view of recent user interactions; validating that answers are being stored. |
| GET | `/api/user/monitoring/response-log` | Returns recent responses from DB (last 24h) with latency + token metadata. Supports `?limit=`. | Performance troubleshooting, token usage review, auditing last responses. |
| GET | `/api/user/monitoring/resources` | Computes KB resource stats from DB (chunks, file types, sources) and updates `monitoring.resources`. | Validating ingestion, understanding KB size/composition. |
| POST | `/api/user/monitoring/rag-settings` | Updates in-memory RAG settings (`monitoring.update_rag_settings(...)`). | Runtime tuning without redeploy (typically resets on restart unless persisted elsewhere). |
| POST | `/api/user/monitoring/model-settings` | Updates in-memory model settings (`monitoring.update_model_settings(...)`). | Runtime model tuning without redeploy (typically resets on restart). |
| GET | `/api/user/monitoring/sessions` | Session activity snapshot (last 24h) with query counts; attempts to create `sessions` table if missing. | Ops view of active/recent sessions; validating session tracking + usage. |

---

## 3. Legacy Session Endpoints — `/api/user/session/*`

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| POST | `/api/user/session/track` | Track/update session activity using `src.auth_service.application.session_service.track_session`. | Called by app flows to keep session “last activity” and query counts updated. |
| GET | `/api/user/session/list` | List all sessions ordered by last activity (DB). | Admin/support “sessions list” page and audits. |

---

## 4. Endpoint Status Dashboard — `/api/user/endpoints-status`

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| GET | `/api/user/endpoints-status` | Checks status of key endpoints across **User**, **Cleaning**, and **Ingestion** services (route existence + real HTTP GETs where applicable). Returns per-endpoint status + response time and an overall status. | “Single pane of glass” during ops incidents; quickly identify which service/dependency is down. |

---

## 5. Chat Sessions CRUD (Admin) — `/api/user/sessions*`

These endpoints manage **persisted chat sessions** (DB records). They are implemented using `src.db_service.crud` + `src.shared.schemas`.

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| POST | `/api/user/sessions` | Create a chat session (generates UUID if omitted). | Admin tools; internal flows that need explicit session record creation. |
| GET | `/api/user/sessions/{session_id}` | Fetch one session by `session_id`. | Support/debug; session inspection. |
| GET | `/api/user/sessions?user_id=...&limit=...` | List sessions for a given user ordered by updated time. | History sidebar / “my sessions” UI; support queries. |
| PATCH | `/api/user/sessions/{session_id}` | Update session fields. | Rename/title updates, admin corrections. |
| PATCH | `/api/user/sessions` | Update a session using `session_id` in request body. | Same as above; alternative request shape. |
| DELETE | `/api/user/sessions/{session_id}` | Delete a session (and cascades messages). | Cleanup, GDPR-style deletion flows, admin resets. |

---

## 6. Messages CRUD (Admin) — `/api/user/messages*`

These endpoints manage **persisted chat messages** (DB records), which link a session to a query/response pair.

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| POST | `/api/user/messages` | Create a chat message (requires existing session + query + response records). | Persisting conversation history for UI and audits. |
| GET | `/api/user/messages/{message_id}` | Fetch one message by DB ID. | Support/debug; targeted inspection. |
| GET | `/api/user/messages?session_id=...&favourites_only=...&limit=...` | List messages in a session; optionally only favourites. | Chat transcript UI; favourites view. |
| PATCH | `/api/user/messages/{message_id}` | Update message (react/tags/feedback). Optional `user_id` performs ownership check; admin can omit. | User feedback & favourites; moderation; tagging. |
| DELETE | `/api/user/messages/{message_id}` | Delete message. | Moderation/cleanup. |

---

## 7. Subscriptions CRUD (Admin) — `/api/user/subscriptions*`

These endpoints manage a user’s subscription/plan record (entitlements, usage limits).

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| POST | `/api/user/subscriptions` | Create subscription (fails if already exists). | Provisioning users, plan assignment. |
| GET | `/api/user/subscriptions/{user_id}` | Get subscription by user_id. | Checking entitlements; UI account plan view. |
| PATCH | `/api/user/subscriptions/{user_id}` | Update subscription (plan/features/limits/expires). | Upgrades/downgrades, admin adjustments. |
| DELETE | `/api/user/subscriptions/{user_id}` | Delete subscription. | Deprovisioning, reset. |

---

## 8. File Upload Records CRUD (Admin) — `/api/user/files*`

These endpoints manage **upload metadata records** (not the physical file deletion).

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| POST | `/api/user/files` | Record a file upload; can link to a chat session. | “My uploads” UI; audit trail of uploaded docs. |
| GET | `/api/user/files/{file_id}` | Fetch upload metadata record by ID. | Inspect specific upload entry. |
| GET | `/api/user/files?user_id=...&session_id=...&folder=...&limit=...` | List uploads for a user; optional filtering by session and `folder` (tags like GST/IT/ETC). | Upload history view; filtering/tag browsing. |
| PATCH | `/api/user/files/{file_id}` | Update upload metadata (tags). | Organizing uploads; categorization. |
| DELETE | `/api/user/files/{file_id}` | Delete upload record only (does **not** delete stored file). | Metadata cleanup; storage deletion is separate. |

---

## 9. Placeholders / Static Info — `/api/user/*`

| Method | Path | Purpose | When it comes into picture |
|--------|------|---------|----------------------------|
| GET | `/api/user/subscription/plans` | Static plan definitions (free/pro/enterprise). | UI can show plan options without billing integration. |
| GET | `/api/user/privacy/info` | Static privacy info (placeholder). | UI privacy/compliance page display. |

---

## Notes (Ops & Security)

- **Sensitive data**: Some endpoints can expose query/response history, tokens, session identifiers, and operational details. In production, these are typically **admin-only** (protected via auth/roles or internal-network access).
- **Runtime settings**: `rag-settings` / `model-settings` update **in-memory** state; changes may be lost on restart unless persisted elsewhere.

