# Query-to-Response Walkthrough — LLM User Service

> **Purpose:** This document describes what happens when a user submits a query in this project: the full flow from request to persisted response, **which data is saved first**, and **how responses are generated**.  
> **Last updated:** 2026-03-06

---

## 1. High-Level Overview

When a user sends a question (via **POST `/api/user/chat`** or **POST `/api/user/query`**), the system:

1. **Resolves or creates a chat session** (so every query belongs to a session).
2. **Stores the user’s question first** (in `user_queries`).
3. **Runs the RAG pipeline** (query expansion → retrieval → reranking → context building → LLM call).
4. **Saves the generated answer** (in `query_responses`).
5. **Links question and answer** in the UI layer (in `chat_messages`).

So the **order of persistence is: Query first, then Response, then ChatMessage**.

---

## 2. Entry Points

| Endpoint | Auth | Typical use |
|----------|------|-------------|
| **POST `/api/user/chat`** | Required (cookie / Bearer) | Main chat UI: sends `question`, optional `session_id` to continue a conversation. |
| **POST `/api/user/query`** | Optional | RAG pipeline with full `QueryCreate` schema (e.g. `query_text`, `session_id`, `user_id`). |

Both endpoints delegate to **`ChatService.process_chat()`** in `src/chat_service/application/chat_service.py`. The rest of this walkthrough follows that single flow.

---

## 3. Step-by-Step Process (What Happens and What Is Saved)

### Step 1: Session setup

- **Code:** `_ensure_session(payload)`  
- **Purpose:** Ensure the request has a valid **chat session** (so we can attach the query and later the message to it).

**Behaviour:**

- If the client sends a **`session_id`** (e.g. from sessionStorage):
  - Backend checks that a **ChatSession** exists for that `session_id` and that it belongs to the current **user_id** (e.g. email from JWT).
  - If valid → **reuse** that session; no new row.
- If no `session_id` or it’s invalid/unauthorized:
  - **Create a new ChatSession** via `create_new_session(db, user_id)` in `src/auth_service/application/session_service.py`.
  - New row in **`chat_sessions`** with `user_id`, `session_id` (e.g. `DDMMYYYY-<uuid>`), `created_at`, `updated_at`.

**Saved here:** Only when a new conversation is started → one new row in **`chat_sessions`**.

---

### Step 2: First-message title (sidebar)

- **Code:** `store_first_message(payload.session_id, question)`  
- **Purpose:** For the **first** user message in this session, generate a short title and store it in the session’s `history` JSON (for sidebar display).

**Behaviour:**

- Load **ChatSession** by `session_id`.
- If `history` already has a `title` → do nothing.
- Otherwise:
  - Generate a title (e.g. via LLM) from the first question.
  - Update **`chat_sessions.history`** with `{"title": "...", "first_question": "..."}` via `crud.update_chat_session_history()`.

**Saved here:** Update to **`chat_sessions.history`** (no new table; only when this is the first message in the session).

---

### Step 3: Save the query (first persistent record of the turn)

- **Code:** `crud.create_query(self.db, payload)`  
- **Purpose:** Persist the user’s question **before** any RAG or LLM work, so every request is recorded even if the pipeline fails later.

**Behaviour:**

- Build a **UserQuery** from `payload` (`query_text`, `user_id`, `session_id`, `language`, `is_temporary`, etc.).
- **INSERT** into **`user_queries`**.
- **Commit** in `crud.create_query()` (see `src/db_service/crud.py`).

**Saved here:** One new row in **`user_queries`** (id, query_text, user_id, session_id, created_at, …).  
**This is the first save in the query→response flow.**

---

### Step 4: Track session activity

- **Code:** `_track_session(payload.session_id)`  
- **Purpose:** Update the legacy **sessions** table (if used) for activity and query count.

**Behaviour:**

- Calls `track_session(db, session_id)` in `src/auth_service/application/session_service.py`.
- If a row exists in **`sessions`** for that `session_id`, it updates `last_activity_at` and increments `query_count`; otherwise it may create a row.

**Saved here:** Update (or insert) in **`sessions`** (separate from `chat_sessions`; used for activity/metrics).

---

### Step 5: Query expansion (optional)

- **Code:** `_expand_query(question, query_expansion_enabled, expansion_strategy)`  
- **Purpose:** Optionally rephrase or expand the question to improve retrieval (e.g. synonyms, multi-angle queries).

**Behaviour:**

- If disabled → returns original question and empty important words.
- If enabled → uses **query_expansion_service** (e.g. LLM or rule-based) and returns:
  - **expanded_query** (string used for retrieval),
  - **important_words** (used later for highlighting in the answer).

**Saved here:** Nothing. Purely in-memory for this request.

---

### Step 6: Retrieval (get relevant chunks from the knowledge base)

- **Code:** `_retrieve_documents(question, expanded_query, limit, reranking_enabled, hybrid_retrieval_enabled)`  
- **Purpose:** Fetch document chunks from the vector store (and optionally sparse search) that are relevant to the (expanded) query.

**Behaviour:**

- Encode **expanded_query** (or original question) with the **embedding model** (e.g. `SentenceTransformer("all-MiniLM-L6-v2")`).
- If **hybrid_retrieval_enabled**:
  - Uses **hybrid_retrieve()** (dense vectors + sparse/BM25) from `src/vector_service/infrastructure/hybrid_retrieval.py` and search_service.
- Else:
  - Uses **semantic_search()** (dense only) from `src/vector_service/infrastructure/vector_search.py`.
- Returns a list of **chunks** (each with `id`, `text`, `metadata`, `score`).  
- Search uses **PostgreSQL + pgvector** (and optionally a sparse index) via the DB session.

**Saved here:** Nothing. Reads from **`document_chunks`** (and related tables); no write in this step.

---

### Step 7: Reranking and preparation

- **Code:** `_prepare_content(chunks, question, limit, reranking_enabled, reranker_type)`  
- **Purpose:** Rerank and trim chunks so only the most relevant ones are sent to the LLM.

**Behaviour:**

- Filter out chunks with empty text.
- If **reranking_enabled** and chunks exist:
  - Call **reranking_service** (e.g. cross-encoder, Cohere, BGE, or LLM-based reranker) to score chunks against the **original question**.
- Take top **limit** chunks (e.g. 5).

**Saved here:** Nothing. In-memory only.

---

### Step 8: Context building

- **Code:** `_build_context(chunks)`  
- **Purpose:** Turn the selected chunks into a single **context string** for the LLM prompt (with length limits to avoid token overflow).

**Behaviour:**

- Concatenate chunk texts with source labels, respecting **MAX_CONTEXT_CHARS** and **MAX_CHUNKS_FOR_CONTEXT** (and per-chunk truncation).
- Returns one string, e.g. `"[Source: doc1]\n...\n\n[Source: doc2]\n..."`.

**Saved here:** Nothing. In-memory only.

---

### Step 9: Prompt selection and LLM call (how the response is generated)

- **Code:** `_generate_answer(question, context, chunks, important_words)`  
- **Purpose:** Choose the right prompt template, build the full prompt, call the LLM, then post-process the answer.

**Behaviour:**

1. **Template detection**  
   - `detect_template_from_question(question)` (in `src/rag_service/infrastructure/prompt_templates.py`) inspects the question (e.g. “what is X”, “how to do Y”, numbers/tax/computation) and returns:
   - **template_id** (e.g. `rag`, `definition`, `computation`, `procedure`),
   - **params** (e.g. `financial_data`, `term`, `process_name`).

2. **Prompt building**  
   - `build_prompt_from_template(template_id, params)` merges:
     - **retrieved_context** (the string from Step 8),
     - **user_query** (original question),
     - and any template-specific params (e.g. `financial_data`, `term`),
   - and returns the final **prompt** string sent to the LLM.

3. **LLM call**  
   - `call_openrouter_chat(prompt, OPENROUTER_API_KEY, model)` (in `src/rag_service/infrastructure/openrouter.py`) sends the prompt to **OpenRouter** (e.g. Mistral or other configured model).
   - Returns **raw answer text** and **usage** (prompt_tokens, completion_tokens, etc.).
   - On suspected truncation, the code may do a single “continue” call and append to the answer.

4. **Post-processing**  
   - **clean_markdown_formatting(raw)** — normalize markdown.
   - If **important_words** exist → **highlight_answer_with_keywords(answer, important_words)**.
   - **tag_response(answer, query)** (tagging_service) → optional tags for the answer.
   - **build_language_response(answer, …)** (e.g. Tamil) → optional **language_response** for multi-language UI.

**Saved here:** Nothing yet. The **answer**, **usage**, **model**, **tags**, **language_response** are only in memory and are persisted in the next step.

---

### Step 10: Save the response (second persistent record)

- **Code:** `_save_response(query_row, answer_data, chunks, start_time)`  
- **Purpose:** Persist the LLM output and metadata linked to the **existing** UserQuery row.

**Behaviour:**

- Build **ResponseCreate** from:
  - **query_id** = `query_row.id` (the UserQuery we inserted in Step 3),
  - **response_text** = final answer,
  - **retrieved_context_ids** = chunk ids used,
  - **llm_model**, **latency_ms**, **prompt_tokens**, **completion_tokens**, **total_tokens**, **tags**, **language_response**.
- **INSERT** into **`query_responses`** via `crud.create_response(self.db, response_create)` and **commit**.

**Saved here:** One new row in **`query_responses`**.  
**So: Query is saved first (Step 3), Response is saved second (Step 10).**

---

### Step 11: Create chat message (link query + response for the UI)

- **Code:** `_create_chat_message(payload.session_id, query_row.id, response_row.id, tags, payload.user_id)`  
- **Purpose:** Create the “message” that the chat UI shows as one turn (user question + assistant reply), and link it to the session.

**Behaviour:**

- Ensures the **ChatSession** exists for `session_id` (e.g. via `get_or_create_session`).
- Build **ChatMessageCreate** with:
  - **session_id**, **query_id**, **response_id**, **tags**, **react** = `"no_react"`.
- **INSERT** into **`chat_messages`** via `crud.create_chat_message()` and **commit**.

**Saved here:** One new row in **`chat_messages`** (session_id, query_id, response_id, react, tags, …).  
**This is the third save: after Query and Response.**

---

### Step 12: Return to client

- The handler (e.g. **POST `/api/user/chat`**) returns a JSON body such as:
  - **answer** / **reply**, **important_words**, **language_response**, **tags**,
  - **query_id**, **response_id**, **message_id**, **session_id**.

The frontend can then display the answer and, if needed, refetch or update the message (e.g. reactions) using these IDs.

---

## 4. Order of Saves (Summary)

| Order | What is saved | Table | When |
|-------|----------------|-------|------|
| 1 | Chat session (if new) | **chat_sessions** | Step 1 – session setup |
| 2 | Session title / first question (if first message) | **chat_sessions.history** | Step 2 – store_first_message |
| 3 | User question | **user_queries** | Step 3 – create_query |
| 4 | Session activity | **sessions** | Step 4 – track_session |
| 5 | LLM answer + metadata | **query_responses** | Step 10 – create_response |
| 6 | One “turn” in the chat | **chat_messages** | Step 11 – create_chat_message |

So: **query is saved first**, then **response**, then the **chat message** that ties them together for the UI.

---

## 5. Error Handling and Fallbacks

- **RAG/LLM failure:** If anything in Steps 5–9 throws (e.g. retrieval or LLM error), the service still:
  - Uses the **already-saved** UserQuery (Step 3).
  - Builds a fallback **answer_data** (e.g. “System temporary issue. Please try again.”).
  - **Saves a QueryResponse** (Step 10) with that fallback text so the user sees a consistent message and the turn is still stored.
- **ChatMessage creation failure:** If Step 11 fails, the API still returns the answer and IDs; only the **chat_messages** row might be missing, which can affect sidebar/history consistency until fixed.

---

## 6. Key Files Reference

| Concern | File(s) |
|--------|---------|
| Entry (chat/query) | `src/chat_service/api/routes.py` |
| End-to-end flow & order of saves | `src/chat_service/application/chat_service.py` → `process_chat()` |
| Session (create/continue) | `src/auth_service/application/session_service.py` |
| Persist query | `src/db_service/crud.py` → `create_query()` |
| Persist response | `src/db_service/crud.py` → `create_response()` |
| Persist chat message | `src/db_service/crud.py` → `create_chat_message()` |
| Retrieval (vector / hybrid) | `src/vector_service/infrastructure/vector_search.py`, `hybrid_retrieval.py` |
| Reranking | `src/rag_service/infrastructure/reranking_service.py` |
| Prompt choice & build | `src/rag_service/infrastructure/prompt_templates.py` |
| LLM call | `src/rag_service/infrastructure/openrouter.py` |
| Models (tables) | `src/db_service/models.py` (UserQuery, QueryResponse, ChatSession, ChatMessage) |

---

## 7. Data Model (Relevant Tables)

- **chat_sessions** — One row per conversation; `history` JSON holds title and first question.
- **user_queries** — One row per user question; has `session_id` (FK to chat_sessions).
- **query_responses** — One row per LLM answer; has `query_id` (FK to user_queries).
- **chat_messages** — One row per visible “turn”; links `session_id`, `query_id`, `response_id` (and react/tags/feedback).

Together, a single user message flow creates or reuses: **1 ChatSession** (if new), **1 UserQuery**, **1 QueryResponse**, and **1 ChatMessage**, in that logical order.
