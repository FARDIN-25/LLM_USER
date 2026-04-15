# PostgreSQL FTS Optimization (Sparse Search)

This module implements the Sparse Search (Keyword) side of our Hybrid RAG Retrieval system. It has been optimized from legacy literal matching to advanced, natural-language query processing.

## 🚀 Key Upgrades
* **Replaced `plainto_tsquery` with `websearch_to_tsquery`**: Vastly reduces "no results" errors by intelligently parsing natural language exactly like Google Search does.
* **Unified Dual-Table Querying**: Simultaneously hunts for exact keywords in both `docs_chunks` and `book_chunks` in a single optimized database call.
* **SQL NULL Guards**: Built-in safeguards preventing backend crashes on edge-cases (like pure stop-word queries).

## 🔥 Using the Search Engine

The FTS component allows for advanced user queries. Users can now type queries like:

* Standard text: `income tax slabs 2024`
* Exact phrases: `"reverse charge mechanism"` 
* Exclusions: `GST -penalty`

## 🛠 Required Setup (Database)

Ensure your database has the requisite `GIN` indexes activated. The migration script (`unified_rag_refactor.sql`) handles this natively:

```sql
CREATE INDEX IF NOT EXISTS idx_docs_fts ON docs_chunks USING GIN (fts_vector);
CREATE INDEX IF NOT EXISTS idx_books_fts ON book_chunks USING GIN (fts_vector);
```

## 📊 Analytics & Observability

The application seamlessly tracks sparse retrieval success. Check your server logs for the following trace pattern to debug matching success:
`🔍 Sparse search (FTS) k=5: 'GST penalties'`
`FTS Query: GST penalties, Results: 10`

## Maintainer Note
If adjusting scoring weights, do NOT edit this module directly. Modify the weight injection inside the `hybrid_retrieve` aggregator to maintain the mathematical integrity of the `rank / (rank + 1)` normalization logic.
