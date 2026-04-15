# RAG System: User Query to Answer — Full KT (Knowledge Transfer)

This document explains **step-by-step** how a user’s question flows through the system: from the API entry point → query expansion → hybrid retrieval → reranking → prompt templates → LLM answer → database storage.  
It is written for **freshers** and includes **file names and line numbers** for each step.

---

## Table of Contents

1. [High-Level Flow Diagram](#1-high-level-flow-diagram)
2. [Where the User Query Starts (Entry Point)](#2-where-the-user-query-starts-entry-point)
3. [Step-by-Step Process with Files and Lines](#3-step-by-step-process-with-files-and-lines)
4. [Query Expansion — Deep Dive](#4-query-expansion--deep-dive)
5. [Query Expansion — Deep Details (Step-by-Step & Core Logic)](#5-query-expansion--deep-details-step-by-step--core-logic)
6. [Hybrid Retrieval — Deep Dive](#6-hybrid-retrieval--deep-dive)
7. [Reranking — Deep Dive](#7-reranking--deep-dive)
8. [Prompt Templates — Deep Dive](#8-prompt-templates--deep-dive)
9. [How Data Is Stored in the Database](#9-how-data-is-stored-in-the-database)
10. [End-to-End Flow Summary Table](#10-end-to-end-flow-summary-table)

---

## 1. High-Level Flow Diagram

```
                    USER ASKS A QUERY
                            |
                            v
    +----------------------------------------------------------+
    |  ENTRY: routes.py (Chat/Query API)                        |
    |  File: src/chat_service/api/routes.py                     |
    +----------------------------------------------------------+
                            |
                            v
    +----------------------------------------------------------+
    |  ORCHESTRATION: ChatService.process_chat()                 |
    |  File: src/chat_service/application/chat_service.py       |
    +----------------------------------------------------------+
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
   Save Query          Query Expansion      (continues below)
   (DB: user_queries)       |
        |                   v
        |    +----------------------------------------------------------+
        |    |  QUERY EXPANSION                                          |
        |    |  query_expansion_service.py + tax_vocabulary.py           |
        |    +----------------------------------------------------------+
        |                    |
        |                    v
        |    +----------------------------------------------------------+
        |    |  HYBRID RETRIEVAL (or Dense-only)                         |
        |    |  hybrid_retrieval.py / search_logic.py / vector_search   |
        |    +----------------------------------------------------------+
        |                    |
        |                    v
        |    +----------------------------------------------------------+
        |    |  RERANKING                                                |
        |    |  reranking_service.py                                     |
        |    +----------------------------------------------------------+
        |                    |
        |                    v
        |    +----------------------------------------------------------+
        |    |  PROMPT TEMPLATES                                         |
        |    |  prompt_templates.py (detect + build_prompt)               |
        |    +----------------------------------------------------------+
        |                    |
        |                    v
        |    +----------------------------------------------------------+
        |    |  LLM GENERATION (OpenRouter) → Answer                     |
        |    |  openrouter.py + llm_service.py                           |
        |    +----------------------------------------------------------+
        |                    |
        +--------------------+
                            |
                            v
    +----------------------------------------------------------+
    |  SAVE RESPONSE + CHAT MESSAGE (DB)                        |
    |  crud.py: create_response, create_chat_message            |
    |  Tables: query_responses, chat_messages                    |
    +----------------------------------------------------------+
                            |
                            v
                      ANSWER TO USER
```

---

## 2. Where the User Query Starts (Entry Point)

When a user sends a question, the **first code that runs** is in the **chat/query API routes**.

### 2.1 File and code that handle the user query

| Endpoint | File | Line range | Purpose |
|----------|------|------------|---------|
| **POST /chat** | `src/chat_service/api/routes.py` | **30–96** | Chat endpoint: accepts `question` or `query_text`, builds `QueryCreate`, calls `ChatService.process_chat()`. |
| **POST /query** | `src/chat_service/api/routes.py` | **99–130** | Full RAG pipeline: accepts `QueryCreate`, calls `ChatService.process_chat()` with expansion/reranking/hybrid options. |

**How routes are mounted (so you know the full URL):**

- In **`src/main.py`** (around **385–387**):
  - `app.include_router(chat_routes.router, prefix="/api/user")`  
  - `app.include_router(chat_routes.router)` (no prefix)

So the user can call:

- **`POST /api/user/chat`** or **`POST /chat`**
- **`POST /api/user/query`** or **`POST /query`**

**Relevant code (entry):**

- **`routes.py`** lines **44–45**: `question = payload.get("question") or payload.get("query_text")`
- **`routes.py`** lines **68–75**: `service = ChatService(db, embedding_model)` then `result = await service.process_chat(...)`

So: **the flow starts in `src/chat_service/api/routes.py`** (chat or query endpoint), then immediately goes to **`ChatService.process_chat()`** in **`src/chat_service/application/chat_service.py`**.

---

## 3. Step-by-Step Process with Files and Lines

All steps below happen inside **`ChatService.process_chat()`** unless stated otherwise.

| Step | What happens | File | Line(s) |
|------|----------------|------|--------|
| 1 | Get question from payload | `chat_service.py` | 51: `question = payload.get_question_text()` |
| 2 | Ensure session (create session_id if missing) | `chat_service.py` | 57: `self._ensure_session(payload)` |
| 3 | **Save initial query to DB** | `chat_service.py` | 60: `query_row = crud.create_query(self.db, payload)` → **`crud.py`** **14–27**: `create_query()` → table **`user_queries`** |
| 4 | **Query expansion** | `chat_service.py` | 65–67: `expanded_query, important_words = self._expand_query(...)` → see [Section 4](#4-query-expansion--deep-dive) |
| 5 | **Retrieval** (hybrid or dense) | `chat_service.py` | 70–76: `chunks = await self._retrieve_documents(...)` → see [Section 5](#5-hybrid-retrieval--deep-dive) |
| 6 | **Reranking & prepare content** | `chat_service.py` | 79–85: `chunks = self._prepare_content(...)` → see [Section 6](#6-reranking--deep-dive) |
| 7 | Build context string from chunks | `chat_service.py` | 88: `context = self._build_context(chunks)` (253–273) |
| 8 | **Prompt template + LLM → answer** | `chat_service.py` | 91–95: `answer_data = await self._generate_answer(...)` → see [Section 7](#7-prompt-templates--deep-dive) |
| 9 | **Save response to DB** | `chat_service.py` | 98–102: `response_row = self._save_response(...)` → **`crud.py`** **58–77**: `create_response()` → table **`query_responses`** |
| 10 | Create chat message (link query + response) | `chat_service.py` | 105–110: `_create_chat_message(...)` → **`crud.py`** **146–159**: `create_chat_message()` → table **`chat_messages`** |
| 11 | Return answer and IDs to API | `chat_service.py` | 113–122: `return { "answer": ..., "query_id", "response_id", ... }` |

So: **query expansion** is triggered at **`chat_service.py`** lines **65–67**, and it **connects** to the expansion service and tax vocabulary as described in the next section.

---

## 4. Query Expansion — Deep Dive

**Purpose:** Turn the user’s short question into a richer “search query” (and get “important words” for highlighting) so retrieval finds more relevant chunks.

### 4.1 Where it is called

- **File:** `src/chat_service/application/chat_service.py`
- **Method:** `_expand_query(self, query, enabled, strategy)`
- **Called from:** `process_chat()` at **lines 65–67**:
  - `expanded_query, important_words = self._expand_query(question, query_expansion_enabled, expansion_strategy)`

### 4.2 Flow inside the code

1. **`_expand_query`** (chat_service.py **145–164**):
   - If expansion is disabled → returns `(query, [])`.
   - Otherwise:
     - Gets **QueryExpansionService** from **`src/rag_service/application/query_expansion_service.py`**: `get_expansion_service()`.
     - Parses strategy with **`parse_strategy(strategy or settings.QUERY_EXPANSION_STRATEGY)`** (query_expansion_service.py **29–36**).
     - Calls **`service.expand(query, strat_enum, max_tokens=200, use_important_words=True)`** (query_expansion_service.py **104–172**).
   - From the result it takes:
     - **expanded_queries[0]** → `expanded_query`
     - **important_words** → `important_words`
   - Returns `(expanded, words)`.

2. **QueryExpansionService.expand()** (query_expansion_service.py **104–172**):
   - Chooses strategy: **static**, **llm**, **hybrid**, **module_wise**, **token_optimized** (or default hybrid/static).
   - Dispatches to:
     - **`_expand_static`** (173–239) — uses **tax_vocabulary.expand_query**
     - **`_expand_llm`** (383–433) — uses OpenRouter LLM to expand
     - **`_expand_hybrid`** (435–406) — static + LLM
     - **`_expand_module_wise`** (408–419) — static + module keywords
     - **`_expand_token_optimized`** (421–440) — static + token limit

3. **Static expansion and tax_vocabulary:**
   - **`_expand_static`** (query_expansion_service.py **183–184**): `result = self._static_expand_func(query)`.
   - That function is set in **`_init_static_expansion`** (query_expansion_service.py **63**):  
     `from .query_expansion.tax_vocabulary import expand_query as static_expand`  
     So **`expand_query`** in **`src/rag_service/application/query_expansion/tax_vocabulary.py`** is the core.

4. **tax_vocabulary.expand_query** (tax_vocabulary.py **12240–12480**):
   - **12241–12243:** Normalizes the user query.
   - **12244–12247:** Initializes `expanded` (set of query variants) and `important_words`, `matched_concepts`.
   - **12249–12310:** Loops over **DOMAIN_KNOWLEDGE**. For each concept:
     - Matches concept, routing_keywords, semantic_synonyms, and many keyword categories (e.g. appointment_keywords, section references, etc.).
     - If matched: adds synonyms, subtopics, routing_keywords, user_query_variants, semantic_synonyms, core_concepts, legal_sections, procedures, forms, and all keyword categories to `expanded` and `important_words`.
   - **12465–12469:** Adds important words from the original query.
   - **12474–12480:** Returns:
     - `original_query`, `normalized_query`, **`expanded_queries`** (list of expanded strings), **`important_words`**, **`matched_concepts`**.

5. **Mappings (sections, forms, acronyms, legal aliases):**
   - **query_expansion_service.py** **241–318**: **`_apply_comprehensive_mappings`** uses:
     - **`mappings.find_sections_in_query`**, **`get_section_info`**
     - **`mappings.find_forms_in_query`**, **`get_form_info`**
     - **`mappings.find_acronyms_in_query`**, **`expand_acronym`**
     - **`mappings.get_legal_aliases`**
   - These live in **`src/rag_service/application/query_expansion/mappings.py`**.

### 4.3 Summary: Query expansion connection

- **Starts:** `chat_service.py` **65–67** (`_expand_query`).
- **Service:** `query_expansion_service.py` (`get_expansion_service()`, `expand()`, `_expand_static` / `_expand_hybrid` / etc.).
- **Core expansion logic:** `tax_vocabulary.py` **12240–12480** (`expand_query`).
- **Extra mappings:** `query_expansion_service.py` **241–318** + **mappings.py**.

The **expanded query** (and optionally multiple variants) is then passed to **retrieval**; **important_words** are used later for highlighting in the answer.

---

## 5. Query Expansion — Deep Details (Step-by-Step & Core Logic)

This section walks through **exactly how query expansion works** when a user asks a query: every step, with **file names and line numbers**, and the **core logic** at each step. No code changes—explanation only.

### 5.1 Overview: What query expansion does

- **Input:** The user’s raw question (e.g. *"What is GSTR-3B?"*).
- **Output:**  
  - **Expanded query (or list of variants):** Richer text used for retrieval (e.g. original + "monthly summary return", "GSTR3B", "monthly return").  
  - **Important words:** Terms used later to highlight the answer (e.g. "GSTR-3B", "monthly", "return").
- **Why:** Short or jargon-heavy queries often miss relevant chunks; expansion adds synonyms and related terms so retrieval finds more relevant documents.

---

### 5.2 Step-by-step process (user query → expanded query + important words)

#### Step 1: User query reaches the pipeline

| What | File | Line(s) | Explanation |
|------|------|--------|--------------|
| User sends question (e.g. POST /chat or /query) | `src/chat_service/api/routes.py` | **44–45** (chat), **101–102** (query) | Request body is read; `question` = `payload.get("question")` or `payload.get("query_text")`. |
| Orchestrator receives question | `src/chat_service/application/chat_service.py` | **51** | `question = payload.get_question_text()` inside `process_chat()`. |
| Query expansion is invoked | `src/chat_service/application/chat_service.py` | **65–67** | `expanded_query, important_words = self._expand_query(question, query_expansion_enabled, expansion_strategy)`. |

So the **first place** query expansion is triggered is **`chat_service.py` lines 65–67**.

---

#### Step 2: Entry into expansion — `_expand_query`

| What | File | Line(s) | Core logic |
|------|------|--------|------------|
| Check if expansion is disabled | `src/chat_service/application/chat_service.py` | **146–147** | `if not enabled: return query, []`. If expansion is off, original query and no important words are returned. |
| Import expansion service and parse strategy | `src/chat_service/application/chat_service.py` | **149–152** | Imports `get_expansion_service` and `parse_strategy` from **query_expansion_service.py**. Gets singleton service; converts strategy string (e.g. `"hybrid"`, `"static"`) to **ExpansionStrategy** enum. |
| Call service.expand() | `src/chat_service/application/chat_service.py` | **154** | `result = service.expand(query, strat_enum, max_tokens=200, use_important_words=True)`. All expansion strategies are executed inside this call. |
| Unpack result for pipeline | `src/chat_service/application/chat_service.py` | **156–161** | `expanded_queries` → take first element as `expanded_query`. `important_words` → filter to non-empty strings. Return `(expanded, words)`. |
| On exception | `src/chat_service/application/chat_service.py` | **162–164** | Log warning and return `(query, [])` so the rest of the pipeline still runs with the original query. |

---

#### Step 3: Strategy selection — `expand()` and `parse_strategy`

| What | File | Line(s) | Core logic |
|------|------|--------|------------|
| Empty query guard | `src/rag_service/application/query_expansion_service.py` | **124–129** | If query is empty or whitespace, return `{ "expanded_queries": [query], "important_words": [], "strategy_used": "none" }`. |
| Parse strategy string to enum | `src/rag_service/application/query_expansion_service.py` | **29–36** (`parse_strategy`) | Converts API/config value (e.g. `"hybrid"`, `"static"`, `None`) to **ExpansionStrategy**. Invalid/None → **static**. |
| Choose strategy if None | `src/rag_service/application/query_expansion_service.py` | **131–146** | If strategy is None: prefer **hybrid** → else **static** → else **llm**. If none available, return original query with `strategy_used: "none"`. |
| Dispatch to strategy method | `src/rag_service/application/query_expansion_service.py` | **148–164** | **static** → `_expand_static`. **llm** → `_expand_llm`. **hybrid** → `_expand_hybrid`. **module_wise** → `_expand_module_wise`. **token_optimized** → `_expand_token_optimized`. |
| On exception | `src/rag_service/application/query_expansion_service.py` | **165–172** | Log error and return original query with `strategy_used: "error"` and `error` message. |

---

#### Step 4: Static expansion path — `_expand_static` and tax_vocabulary

This is the **main path** when strategy is **static** or the base for **hybrid**, **module_wise**, and **token_optimized**.

| What | File | Line(s) | Core logic |
|------|------|--------|------------|
| Guard: static not available | `src/rag_service/application/query_expansion_service.py` | **175–181** | If `_static_expansion_available` is False (e.g. tax_vocabulary import failed at startup), return original query and empty important_words. |
| Call core expand function | `src/rag_service/application/query_expansion_service.py` | **183–184** | `result = self._static_expand_func(query)`. This is **tax_vocabulary.expand_query** (set at init, line **63**). |
| Validate result shape | `src/rag_service/application/query_expansion_service.py` | **186–194** | If result is not a dict, return original query with error. |
| Normalize expanded_queries list | `src/rag_service/application/query_expansion_service.py` | **196–206** | Get `expanded_queries` from result; ensure it’s a list of strings, strip, remove None, cap at 10. |
| Apply comprehensive mappings | `src/rag_service/application/query_expansion_service.py` | **207–208** | `enhanced_expansions = self._apply_comprehensive_mappings(query, expanded_queries)`. Adds section, chapter, form, acronym, legal-alias, and TAX_SYNONYMS terms (see Step 5). |
| Build important_words | `src/rag_service/application/query_expansion_service.py` | **210–218** | From result’s `important_words` plus `_extract_mapped_keywords(query, enhanced_expansions)`. Deduplicate and cap at 30. |
| Return static result | `src/rag_service/application/query_expansion_service.py` | **220–231** | Return dict: `expanded_queries` (top 5), `important_words`, `strategy_used: "static"`, `matched_concepts`, `mappings_applied` (sections, forms, acronyms, legal_aliases). |

**Core expansion logic lives in tax_vocabulary:**

| What | File | Line(s) | Core logic |
|------|------|--------|------------|
| **expand_query** entry | `src/rag_service/application/query_expansion/tax_vocabulary.py` | **12239–12243** | **12241:** `normalized = normalize_text(user_query)` (lowercase, strip punctuation, collapse spaces — see **12225–12229**). **12242–12243:** `expanded = set()` and add `normalized`; init `important_words` set and `matched_concepts` list. |
| **DOMAIN_KNOWLEDGE** source | `src/rag_service/application/query_expansion/tax_vocabulary.py` | **6464** | **DOMAIN_KNOWLEDGE** is a large dict: keys = concepts (e.g. "accounting standards", "ifrs", "ind as"); values = dicts with "synonyms", "subtopics", "routing_keywords", "semantic_synonyms", "legal_sections", "forms", many keyword categories, etc. |
| Concept matching loop start | `src/rag_service/application/query_expansion/tax_vocabulary.py` | **12249–12257** | For each `(concept, data)` in **DOMAIN_KNOWLEDGE**: build `concept_pattern` with word boundaries (**12251–12252**). **12255–12257:** If normalized query matches concept → `matched = True`. |
| Routing and semantic match | `src/rag_service/application/query_expansion/tax_vocabulary.py` | **12259–12273** | If not matched: check **routing_keywords** (**12260–12265**); then **semantic_synonyms** (**12267–12273**). Any match → `matched = True`. |
| Keyword categories match | `src/rag_service/application/query_expansion/tax_vocabulary.py` | **12274–12308** | Long list of category names (e.g. appointment_keywords, company_type_keywords, …). For each category, get keywords from `data`; if any keyword matches normalized query (word boundary), set `matched = True` and break. |
| When a concept matches — collect expansions | `src/rag_service/application/query_expansion/tax_vocabulary.py` | **12310–12464** | Add concept to `matched_concepts` and `important_words`. Then add to `expanded` and `important_words`: **synonyms** (12315–12322), **subtopics** (12324–12331), **routing_keywords** (12334–12341), **user_query_variants** (12343–12350), **semantic_synonyms** (12352–12359), **core_concepts** (12361–12368), **legal_sections** (12370–12372), **procedures** (12374–12381), **forms** (12383–12386), and **all keyword categories** (12388–12464) from `all_keyword_categories` dict. |
| Important words from original query | `src/rag_service/application/query_expansion/tax_vocabulary.py` | **12465–12469** | Split normalized query into words; add words with length > 3 and not in STOPWORDS to `important_words`. |
| Return from expand_query | `src/rag_service/application/query_expansion/tax_vocabulary.py` | **12474–12480** | Return dict: **original_query**, **normalized_query**, **expanded_queries** = `list(expanded)`, **important_words** = sorted list, **matched_concepts**. |

**Normalize helper:** **tax_vocabulary.py** **12225–12229** (`normalize_query`): lowercase, replace non-alphanumeric (except space/hyphen) with space, collapse spaces, strip.

---

#### Step 5: Comprehensive mappings (sections, forms, acronyms, legal, TAX_SYNONYMS)

After tax_vocabulary returns, the service adds **extra** expansion terms using **mappings** and **TAX_SYNONYMS**.

| What | File | Line(s) | Core logic |
|------|------|--------|------------|
| _apply_comprehensive_mappings entry | `src/rag_service/application/query_expansion_service.py` | **238–248** | `enhanced = set(base_expansions)` (from tax_vocabulary). Import from **mappings.py**: get_section_info, get_chapter_info, get_form_info, expand_acronym, get_legal_aliases, find_sections_in_query, find_forms_in_query, find_acronyms_in_query. |
| Section mapping | `src/rag_service/application/query_expansion_service.py` | **250–259** | **251:** `sections = find_sections_in_query(query)` (**mappings.py 19–20**). For each section, **253:** `get_section_info(section)` (**mappings.py 3–4**). If info exists, add `query + title`, `query + alias` (up to 3), `query + keyword` (up to 3) to `enhanced`. |
| Chapter mapping | `src/rag_service/application/query_expansion_service.py` | **261–270** | Regex for "chapter X" (Roman or digit). For each match, **266:** `get_chapter_info(chapter)` (**mappings.py 6–7**). Add query + chapter title/keywords to `enhanced`. |
| Form mapping | `src/rag_service/application/query_expansion_service.py` | **272–280** | **274:** `forms = find_forms_in_query(query)` (**mappings.py 22–23**). For each form, **276:** `get_form_info(form)` (**mappings.py 8–9**). Add query + form title and aliases to `enhanced`. |
| Acronym expansion | `src/rag_service/application/query_expansion_service.py` | **282–289** | **283:** `acronyms = find_acronyms_in_query(query)` (**mappings.py 25–26**). For each, **285:** `expand_acronym(acronym)` (**mappings.py 13–14**). Add `query + expansion` and query with acronym replaced. |
| Legal aliases | `src/rag_service/application/query_expansion_service.py` | **291–296** | Split query into words; for each word length > 3, **295:** `get_legal_aliases(word)` (**mappings.py 16–17**). Add `query + alias` (up to 2 per word) to `enhanced`. |
| TAX_SYNONYMS injection | `src/rag_service/application/query_expansion_service.py` | **298–306** | Import **TAX_SYNONYMS** from **tax_vocabulary.py** (same file as expand_query; dict of term → list of synonyms). For each term in query_lower, add `query + synonym` (up to 2) to `enhanced`. |
| Return enhanced list | `src/rag_service/application/query_expansion_service.py` | **314** | `return list(enhanced)[:10]`. |

**Note:** **mappings.py** (lines 3–26) currently provides stubs (return None or []). When implemented, section/chapter/form/acronym/legal data will be used here; the flow and line numbers stay the same.

---

#### Step 6: Hybrid strategy (static + LLM)

| What | File | Line(s) | Core logic |
|------|------|--------|------------|
| _expand_hybrid entry | `src/rag_service/application/query_expansion_service.py` | **449–453** | **453:** Call `static_result = self._expand_static(query, use_important_words)` (full static + mappings as above). |
| LLM enhancement | `src/rag_service/application/query_expansion_service.py` | **456–480** | If LLM expansion is available: **458:** `llm_result = self._expand_llm(query, use_important_words)`. **461–466:** Merge: use static expanded_queries, append LLM expanded text if different. **469–472:** Merge important_words from both, dedupe, cap at 20. Return hybrid result with up to 5 expanded_queries. |
| Fallback | `src/rag_service/application/query_expansion_service.py` | **481–484** | On LLM failure or LLM not available, return `static_result` only. |

---

#### Step 7: LLM strategy — `_expand_llm`

| What | File | Line(s) | Core logic |
|------|------|--------|------------|
| Guard | `src/rag_service/application/query_expansion_service.py` | **384–390** | If OPENROUTER_API_KEY not set, return original query and empty important_words. |
| Build prompt | `src/rag_service/application/query_expansion_service.py` | **393–416** | Prompt instructs LLM to expand the user query with synonyms, section numbers, related concepts, alternative phrasings; return only the expanded text (max ~100 words). |
| Call OpenRouter | `src/rag_service/application/query_expansion_service.py` | **420–421** | `result = call_openrouter_chat(prompt, api_key, model)`. |
| Clean response | `src/rag_service/application/query_expansion_service.py` | **422–428** | Take `content`, strip; remove "Expanded Query:"; take first line. If empty or shorter than original, use original query. |
| Important words from LLM text | `src/rag_service/application/query_expansion_service.py` | **431–434** | Split expanded text; filter words length > 3 and not in stopwords; cap at 10. |
| Return | `src/rag_service/application/query_expansion_service.py` | **436–440** | Return single expanded query, important_words, `strategy_used: "llm"`. |

---

#### Step 8: Module-wise and token-optimized (brief)

- **Module-wise** (query_expansion_service.py **486–527**): Calls `_expand_static`, then detects modules (gst, income_tax, compliance, registration) by keywords in query (**494–506**). Adds detected module names to important_words; returns static expanded_queries and enhanced important_words.
- **Token-optimized** (query_expansion_service.py **529–440**): Calls `_expand_static`; estimates tokens (chars/4); fills a list with original query then other expansions until token budget (max_tokens) is reached; may truncate last expansion; returns optimized list and capped important_words.

---

### 5.3 Where the results are used

| Output | Used in | File | Line(s) |
|--------|--------|------|--------|
| **expanded_query** | Retrieval (embedding + search) | `src/chat_service/application/chat_service.py` | **70–76**: passed as `search_query` to `_retrieve_documents(question, expanded_query, ...)`. **178**: `query_embedding = self.embedding_model.encode(search_query)`. So the **expanded** text is what is embedded and searched. |
| **important_words** | Answer highlighting and response | `src/chat_service/application/chat_service.py` | **65–67**: returned with expanded_query. **95**: passed to `_generate_answer(..., important_words)`. **313–316**: `highlight_answer_with_keywords(answer, important_words)` so key terms are emphasized in the UI. **117**: returned in API response as `"important_words"`. |

---

### 5.4 File and line quick reference (query expansion only)

| Component | File | Line(s) |
|-----------|------|--------|
| Trigger | `chat_service.py` | 65–67, 145–164 |
| Strategy parse | `query_expansion_service.py` | 29–36 |
| expand() dispatch | `query_expansion_service.py` | 104–172 |
| _expand_static | `query_expansion_service.py` | 173–239 |
| _apply_comprehensive_mappings | `query_expansion_service.py` | 238–314 |
| _expand_hybrid | `query_expansion_service.py` | 449–484 |
| _expand_llm | `query_expansion_service.py` | 383–448 |
| **Core: expand_query** | **tax_vocabulary.py** | **12239–12480** |
| DOMAIN_KNOWLEDGE | tax_vocabulary.py | 6464 (start) |
| normalize_query | tax_vocabulary.py | 12225–12229 |
| Mappings (stubs) | mappings.py | 1–26 |

---

## 6. Hybrid Retrieval — Deep Dive

**Purpose:** Get document chunks that are relevant to the (expanded) query, using either **dense + sparse (BM25)** together (hybrid) or **dense-only** search.

### 6.1 Where it is called

- **File:** `src/chat_service/application/chat_service.py`
- **Method:** `_retrieve_documents(self, original_query, search_query, limit, reranking_enabled, hybrid_enabled)`
- **Called from:** `process_chat()` at **lines 70–76**, with **search_query = expanded_query**.

### 6.2 Flow inside the code

1. **Embedding the search query** (chat_service.py **174–182**):
   - Uses **`self.embedding_model`** (SentenceTransformer `all-MiniLM-L6-v2`, set in routes.py **24–28**).
   - **Line 178:** `query_embedding = await asyncio.to_thread(self.embedding_model.encode, search_query)`  
   So the **expanded query** is what gets embedded.

2. **If hybrid is enabled** (chat_service.py **186–207**):
   - **188–189:** Imports **`hybrid_retrieve`** and **`get_search_service`** from:
     - **`src/vector_service/infrastructure/hybrid_retrieval.py`** (re-exports from search_logic)
     - **`src/vector_service/infrastructure/search_service.py`**
   - **190–191:** Gets sparse retriever: `sparse = get_search_service().get_retriever()` (BM25).
   - **192–198:** Calls **`hybrid_retrieve(self.db, search_query, query_embedding, sparse, k=search_limit)`**.
   - **199–207:** Converts results to list of dicts with `id`, `text`, `metadata`, `score`.

3. **If hybrid is disabled** (chat_service.py **208–209**):
   - Calls **`semantic_search(self.db, query_embedding, top_k=search_limit)`** from **`src/vector_service/infrastructure/vector_search.py`**.

4. **semantic_search** (vector_search.py **9–51**):
   - **21–27:** Runs SQL on **`document_chunks`**:  
     `ORDER BY embedding <=> (:query_embedding)::vector LIMIT :top_k`  
     (cosine distance with pgvector).
   - Returns list of `{ "id", "text", "content", "metadata" }`.

5. **hybrid_retrieve** (search_logic.py **166–230**):
   - **176:** **Dense:** `dense = dense_search_pgvector(db, query_embedding, k * 2)` (search_logic.py **103–139**).
     - SQL: same table **`document_chunks`**, same vector column, `ORDER BY embedding <=> (:emb)::vector`, returns `id`, `chunk_text`, `metadata`, score.
   - **179–185:** **Sparse:** If `sparse_retriever` is given, `sparse = sparse_retriever.search(query, k * 2)` (BM25 on the same query text).
   - **187–189:** If no sparse results, returns dense-only (first `k`).
   - **192–211:** Normalizes dense and sparse scores, combines with weights (default **weight_dense=0.6**, **weight_sparse=0.4**), sorts by combined score, **deduplicates by document id** (lines 213–227).
   - **230:** Returns top `k` combined results.

### 6.3 Summary: Hybrid retrieval

- **Starts:** `chat_service.py` **70–76** → **165–216** (`_retrieve_documents`).
- **Dense only:** `vector_search.py` **9–51** (`semantic_search`) on **`document_chunks`**.
- **Hybrid:** `search_logic.py` **166–230** (`hybrid_retrieve`) using:
  - **search_logic.py** **103–139** (`dense_search_pgvector`) for dense,
  - BM25 sparse retriever from **search_service** for sparse,
  - then merge, normalize, dedupe, and return top k.

---

## 7. Reranking — Deep Dive

**Purpose:** Take the top chunks from retrieval (e.g. 2× limit when reranking is on), re-score them with a stronger model (cross-encoder / Cohere / BGE / LLM), then apply advanced scoring (exact match, section match, generic penalty) and keep only the best **top_k**.

### 7.1 Where it is called

- **File:** `src/chat_service/application/chat_service.py`
- **Method:** `_prepare_content(self, chunks, query, limit, reranking_enabled, reranker_type)`
- **Called from:** `process_chat()` at **lines 79–85**.

### 7.2 Flow inside the code

1. ** _prepare_content** (chat_service.py **217–252**):
   - **226:** Keeps only valid chunks (non-empty `text`).
   - **229–246:** If reranking is enabled:
     - Imports **`get_reranking_service`**, **`RerankerType`** from **`src/rag_service/infrastructure/reranking_service.py`**.
     - Maps `reranker_type` string to **RerankerType** (e.g. cross-encoder, cohere, bge, llm).
     - **244:** `valid_chunks = service.rerank(query, valid_chunks, limit, r_type)`.
   - **247–248:** If reranking is off or fails, just slices `valid_chunks[:limit]`.
   - Returns the final list of chunks.

2. **RerankingService.rerank()** (reranking_service.py **170–236**):
   - **201:** Limits input to **initial_limit** (default 30) chunks.
   - **204–215:** Chooses reranker type (default: cross-encoder → cohere → bge → llm).
   - **218–236:** Calls the right reranker:
     - **221:** **CROSS_ENCODER:** `_rerank_cross_encoder` (236–271) — sentence-transformers CrossEncoder, pairs (query, chunk_text), predict scores, normalize, sort, return top_k.
     - **222:** **COHERE:** `_rerank_cohere` (273–321) — Cohere rerank API.
     - **223:** **BGE:** `_rerank_bge` (323–375) — BGE model, query–chunk pairs, logits, normalize, sort.
     - **224:** **LLM:** `_rerank_llm` (377–442) — OpenRouter LLM returns a ranking of chunk numbers; parse and assign scores.
   - **231:** After reranker, calls **`_apply_advanced_scoring(query, reranked, top_k)`**.

3. ** _apply_advanced_scoring** (reranking_service.py **445–519**):
   - For each chunk:
     - **479:** `exact_match_score` — phrase/word/bigram match (e.g. query in chunk, word overlap).
     - **480:** `section_match_score` — uses **mappings.find_sections_in_query**, **get_section_info** (reranking_service.py **560** imports from **query_expansion.mappings**).
     - **481:** `generic_penalty` — penalizes generic boilerplate text.
   - **487:** `enhanced_score = base_score + 0.3*exact_match + 0.2*section_match - 0.3*generic_penalty`, clamped to [0,1].
   - Sorts by enhanced score and returns **top_k** chunks (with optional `_rerank_metadata` on each chunk).

### 7.3 Summary: Reranking

- **Starts:** `chat_service.py` **79–85** → **217–252** (`_prepare_content`).
- **Service:** **`src/rag_service/infrastructure/reranking_service.py`**:
  - **170–236:** `rerank()` → cross-encoder / cohere / bge / llm.
  - **445–519:** `_apply_advanced_scoring()` (exact match, section match, generic penalty).
- **Connection to query expansion:** Reranker uses **query** (original user question) and **mappings** (sections/forms) from **query_expansion/mappings.py** for section boost.

---

## 8. Prompt Templates — Deep Dive

**Purpose:** Decide *which* prompt format to use (e.g. RAG, comparison, computation, section_reference) and build the final prompt string that is sent to the LLM with **retrieved context** and **user query**.

### 8.1 Where it is called

- **File:** `src/chat_service/application/chat_service.py`
- **Method:** `_generate_answer(self, query, context, chunks, important_words)`
- **Called from:** `process_chat()` at **lines 91–95**.

### 8.2 Flow inside the code

1. ** _generate_answer** (chat_service.py **275–337**):
   - **285:** **Template detection:**  
     `template_id, params = detect_template_from_question(query)`  
     From **`src/rag_service/infrastructure/prompt_templates.py`**.
   - **286:** `params.update({"retrieved_context": context, "user_query": query})`.
   - **288–289:** If template is **"rag"**, adds **`template_ids_note`** via **`get_rag_template_ids_note()`** (prompt_templates.py **1015–1021**).
   - **291:** **Build prompt:** `prompt = build_prompt_from_template(template_id, params)` (prompt_templates.py **1028–1048**).
   - **296–309:** Calls **`call_openrouter_chat(prompt, ...)`** (OpenRouter LLM), then **`clean_markdown_formatting(raw)`**.
   - **313–316:** If **important_words** exist, **`highlight_answer_with_keywords(answer, important_words)`** (from query expansion).
   - **319–323:** Optional **tag_response** (tags).
   - **326–330:** Optional **build_language_response** (e.g. Tamil).
   - Returns **answer**, **tags**, **language_response**, **usage**, **model**.

2. **detect_template_from_question** (prompt_templates.py **872–~1013**):
   - Takes **question** string.
   - Uses keyword checks to pick **template_id**, e.g.:
     - "difference between", "compare", "vs" → **comparison** (and parses option_a, option_b).
     - "calculate", "how much", "gst on", "tax on" → **computation**.
     - "what is", "define" → **definition**.
     - "section", "section 80" → **section_reference**.
     - Default → **"rag"**.
   - Returns **(template_id, extra_params)**. Extra params (e.g. option_a, option_b, section_number) are merged with **retrieved_context** and **user_query** in chat_service.

3. **build_prompt_from_template** (prompt_templates.py **1028–1048**):
   - Validates **template_id** and **params**.
   - **1041:** Calls **`get_prompt(template_id, **params)`** (prompt_templates.py **1055+**).
   - **get_prompt** finds the template in **PROMPT_LIBRARY** by **id**, merges **default_params** with **kwargs**, and formats the template string (e.g. **"rag"** template at lines **106–142** with rules like "Start with **Answer:**", use bullet "• ", no chunk IDs, etc.).
   - Returns the final prompt string.

### 8.3 Summary: Prompt templates

- **Starts:** `chat_service.py` **91–95** → **275–337** (`_generate_answer`).
- **Detection:** **prompt_templates.py** **872** (`detect_template_from_question`) — picks template from question keywords.
- **Build:** **prompt_templates.py** **1028** (`build_prompt_from_template`) → **1055** (`get_prompt`) → **PROMPT_LIBRARY** (e.g. **rag** at **106–142**).
- **Connection to query expansion:** **important_words** (from query expansion) are used in **highlight_answer_with_keywords** in ** _generate_answer** (chat_service.py **313–316**).

---

## 9. How Data Is Stored in the Database

Storage happens at three points in the flow; all go through **`src/db_service/crud.py`** and use models from **`src/db_service/models.py`**.

### 9.1 Save initial user query

| What | Where | Table | Model |
|------|--------|--------|--------|
| Create user query row | **chat_service.py** line **60**: `crud.create_query(self.db, payload)` | **user_queries** | **UserQuery** (models.py **112–123**) |
| CRUD function | **crud.py** **14–27**: `create_query(db, query)` | same | same |

**Fields stored:** `query_text`, `user_id`, `session_id`, `is_temporary`, `language`, `query_metadata`, `created_at`.

### 9.2 Save response (answer + metadata)

| What | Where | Table | Model |
|------|--------|--------|--------|
| Create response row | **chat_service.py** **98–102**: `response_row = self._save_response(query_row, answer_data, chunks, start_time)` | **query_responses** | **QueryResponse** (models.py **126–139**) |
| _save_response | **chat_service.py** **341–356**: builds **ResponseCreate** (query_id, response_text, retrieved_context_ids, llm_model, latency_ms, tokens, tags, language_response), then **crud.create_response** | same | same |
| CRUD function | **crud.py** **58–77**: `create_response(db, response)` | same | same |

**Fields stored:** `query_id`, `response_text`, `retrieved_context_ids` (array of chunk ids), `llm_model`, `latency_ms`, `response_metadata` (tokens), `tags`, `language_response`, `created_at`.

### 9.3 Save chat message (link query + response for session)

| What | Where | Table | Model |
|------|--------|--------|--------|
| Create chat message | **chat_service.py** **105–110**: `_create_chat_message(payload.session_id, query_row.id, response_row.id, tags)` | **chat_messages** | **ChatMessage** (models.py **68–77**) |
| CRUD function | **crud.py** **146–159**: `create_chat_message(db, msg)` | same | same |

**Fields stored:** `session_id`, `query_id`, `response_id`, `is_favourite`, `tags`, `feedback`, `created_at`.

### 9.4 Process summary

1. **User query** → **chat_service.py** **60** → **crud.create_query** → **user_queries**.
2. **Answer + metadata** → **chat_service.py** **98–102** → **crud.create_response** → **query_responses**.
3. **Session linkage** → **chat_service.py** **105–110** → **crud.create_chat_message** → **chat_messages**.

Knowledge base chunks are stored earlier by the **ingestion** pipeline in **document_chunks** (with **embedding**); retrieval only **reads** from **document_chunks**.

---

## 10. End-to-End Flow Summary Table

| Stage | File(s) | Key function / line | What it does |
|-------|---------|----------------------|--------------|
| **User query entry** | **routes.py** | **30–96** (chat), **99–130** (query) | Receives question, calls **ChatService.process_chat()** |
| **Orchestration** | **chat_service.py** | **32–128** (**process_chat**) | Runs expansion → retrieval → rerank → context → prompt → LLM → save |
| **Save query** | **chat_service.py** → **crud.py** | **60** → **14–27** | **create_query** → **user_queries** |
| **Query expansion** | **chat_service.py** → **query_expansion_service.py** → **tax_vocabulary.py** | **65–67** → **104–172**, **173–239** → **12240–12480** | ** _expand_query** → **expand()** / **_expand_static** → **expand_query()** + mappings |
| **Hybrid retrieval** | **chat_service.py** → **search_logic.py** / **vector_search.py** | **70–76**, **165–216** → **166–230**, **103–139**, **9–51** | ** _retrieve_documents** → **hybrid_retrieve** / **dense_search_pgvector** / **semantic_search** on **document_chunks** |
| **Reranking** | **chat_service.py** → **reranking_service.py** | **79–85**, **217–252** → **170–236**, **445–519** | ** _prepare_content** → **rerank()** → cross-encoder/cohere/bge/llm → **_apply_advanced_scoring** |
| **Context build** | **chat_service.py** | **88**, **253–273** | ** _build_context(chunks)** → single string for prompt |
| **Prompt templates** | **chat_service.py** → **prompt_templates.py** | **91–95**, **275–291** → **872**, **1028**, **1055** | ** _generate_answer** → **detect_template_from_question** → **build_prompt_from_template** → **get_prompt** |
| **LLM + answer** | **chat_service.py** → **openrouter.py** / **llm_service.py** | **296–309**, **313–316** | **call_openrouter_chat(prompt)** → **clean_markdown_formatting** → **highlight_answer_with_keywords(important_words)** |
| **Save response** | **chat_service.py** → **crud.py** | **98–102**, **341–356** → **58–77** | ** _save_response** → **create_response** → **query_responses** |
| **Save chat message** | **chat_service.py** → **crud.py** | **105–110** → **146–159** | ** _create_chat_message** → **create_chat_message** → **chat_messages** |

---

## Quick Reference: “Where does X start?”

- **User asks a query** → **`src/chat_service/api/routes.py`** (POST /chat or /query).
- **Query expansion** → **`src/chat_service/application/chat_service.py`** line **65** (`_expand_query`) → **query_expansion_service.py** + **tax_vocabulary.py** line **12240** (`expand_query`).
- **Hybrid retrieval** → **`chat_service.py`** line **70** (`_retrieve_documents`) → **search_logic.py** `hybrid_retrieve` / **vector_search.py** `semantic_search`.
- **Reranking** → **`chat_service.py`** line **79** (`_prepare_content`) → **reranking_service.py** `rerank()` and `_apply_advanced_scoring()`.
- **Prompt templates** → **`chat_service.py`** line **91** (`_generate_answer`) → **prompt_templates.py** `detect_template_from_question`, `build_prompt_from_template`, `get_prompt`.
- **Database storage** → **chat_service.py** lines **60**, **98–102**, **105–110** → **crud.py** `create_query`, `create_response`, `create_chat_message` → tables **user_queries**, **query_responses**, **chat_messages**.


