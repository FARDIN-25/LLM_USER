# Full-Text Search (FTS) Architecture

## Overview
The RAG system's retrieval layer employs a **Hybrid Search Engine** combining Dense Vector Search (`pgvector`) and Sparse Keyword Search (PostgreSQL FTS). This architecture focuses specifically on the **Sparse Search** component, recently upgraded to utilize `websearch_to_tsquery`.

## Core Components

### 1. Database Layer (PostgreSQL)
- **Table Structure:** Knowledge base is partitioned into two specialized tables: `docs_chunks` (general domain knowledge) and `book_chunks` (structured text).
- **Column (`fts_vector`):** Both tables maintain a `tsvector` column pre-calculated during ingestion to store highly optimized text representations.
- **Indexing:** High-performance `GIN` (Generalized Inverted Index) indexes (`idx_docs_fts` and `idx_books_fts`) map tokens to table rows, making keyword lookups virtually instantaneous even with millions of chunks.

### 2. Application Layer (`search_logic.py`)
- **Query Parsing (`websearch_to_tsquery`):** 
  Unlike `plainto_tsquery` which enforces strict literal inclusion, `websearch_to_tsquery` acts like a modern search engine. It natively understands unquoted text (OR/AND inference), quoted text (exact phrase matching), and negation (`-`), ignoring punctuation and standardizing stop words.
- **Ranking (`ts_rank`):** PostgreSQL natively scores results based on term frequency and proximity. 
- **Sparse Score Normalization:** Because raw `ts_rank` values are unbounded, the application normalizes them into a pristine 0-1 scale using the mathematical formula: `rank / (rank + 1)`.

### 3. Safety Controls & Logging
- **Empty Query Guard:** Drops blank or whitespace-only queries in Python before allocating DB connections.
- **SQL NULL Guard:** `websearch_to_tsquery(:query) IS NOT NULL` actively prevents execution faults on completely ignored queries (e.g., if a user searches for a pure stop-word like "the").
- **Timeouts:** A strict `2s` statement timeout guarantees the UI never hangs.
- **Observability:** Structured logs (`FTS Query: {query}, Results: {count}`) guarantee complete traceability.

## Data Flow
1. User submits natural language query.
2. Python validates query -> skips empty inputs.
3. Query executes concurrently on both `docs_chunks` and `book_chunks`.
4. PostgreSQL translates natural language to syntax tree via `websearch_to_tsquery`.
5. DB rapidly filters rows using `GIN` indexes.
6. DB calculates raw `ts_rank` for matched rows.
7. Python merges the results, normalizes the FTS scores, and feeds them into the overarching Hybrid Scoring algorithm (0.7 Dense + 0.3 Sparse).
