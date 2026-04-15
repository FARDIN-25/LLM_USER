# RAG Service

## Overview

The **RAG Service** provides query enhancement, LLM orchestration, and response optimization for the Retrieval-Augmented Generation pipeline. It handles query expansion, reranking, prompt management, and multi-LLM integration.

## Purpose

- Query expansion with multiple strategies
- LLM integration (OpenRouter, OpenAI, Google AI)
- Result reranking for improved relevance
- Prompt template management
- Multi-language support
- Response post-processing

## Architecture

```
rag_service/
├── api/
│   └── (routes if needed)
├── application/
│   ├── query_expansion_service.py  # Query enhancement
│   ├── multilang_service.py        # Language detection
│   └── tagging_service.py          # Key term extraction
└── infrastructure/
    ├── llm_service.py              # LLM orchestration
    ├── openrouter.py               # OpenRouter integration
    ├── reranking_service.py        # Result reranking
    └── prompt_templates.py         # Prompt management
```

## Key Features

### 1. Query Expansion
- **Multiple Strategies** - Static, LLM, Hybrid, Module-wise, Token-optimized
- **Configurable** - Enable/disable per request
- **Smart Expansion** - Context-aware query enhancement

### 2. LLM Integration
- **Multi-Provider** - OpenRouter, OpenAI, Google AI
- **Retry Logic** - Automatic retry with exponential backoff
- **Timeout Handling** - Configurable timeouts
- **Error Recovery** - Graceful degradation

### 3. Reranking
- **Multiple Rerankers** - Cross-Encoder, Cohere, BGE, LLM
- **Relevance Scoring** - Improve retrieval accuracy
- **Configurable** - Choose reranker per request

### 4. Prompt Management
- **Template System** - Reusable prompt templates
- **Context Injection** - Dynamic context insertion
- **Token Optimization** - Efficient token usage

## Components

### Query Expansion Service

#### Strategies

##### 1. Static Expansion
Predefined term expansions based on domain knowledge.

```python
STATIC_EXPANSIONS = {
    "RAG": ["retrieval augmented generation", "vector search", "semantic search"],
    "LLM": ["large language model", "AI model", "neural network"],
    "embedding": ["vector representation", "semantic encoding"]
}
```

##### 2. LLM Expansion
Use LLM to generate query variations.

```python
def llm_expand(query: str) -> List[str]:
    prompt = f"Generate 3 alternative phrasings for: {query}"
    response = llm_service.generate(prompt)
    return parse_expansions(response)
```

##### 3. Hybrid Expansion
Combines static and LLM expansion.

```python
def hybrid_expand(query: str) -> List[str]:
    static = static_expand(query)
    llm = llm_expand(query)
    return merge_unique(static, llm)
```

##### 4. Module-wise Expansion
Domain-specific expansions for different modules.

```python
def module_wise_expand(query: str, module: str) -> List[str]:
    if module == "finance":
        return finance_expansions(query)
    elif module == "legal":
        return legal_expansions(query)
    # ...
```

##### 5. Token-Optimized Expansion
Minimize token usage while maximizing coverage.

```python
def token_optimized_expand(query: str, max_tokens: int) -> List[str]:
    expansions = generate_all_expansions(query)
    return select_best_within_budget(expansions, max_tokens)
```

#### API

```python
from src.rag_service.application.query_expansion_service import get_expansion_service

expansion_service = get_expansion_service()

# Check availability
if expansion_service.is_available():
    # Get available strategies
    strategies = expansion_service.get_available_strategies()
    
    # Expand query
    expanded = expansion_service.expand_query(
        query="What is RAG?",
        strategy="hybrid"
    )
```

### LLM Service

#### Supported Providers

##### OpenRouter
```python
from src.rag_service.infrastructure.openrouter import call_openrouter_chat

response = call_openrouter_chat(
    prompt="What is RAG?",
    api_key=settings.OPENROUTER_API_KEY,
    model="mistralai/mistral-7b-instruct",
    timeout=20
)
```

##### OpenAI
```python
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}]
)
```

##### Google AI
```python
import google.generativeai as genai

genai.configure(api_key=settings.GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')
response = model.generate_content(prompt)
```

#### Retry Logic

```python
def call_llm_with_retry(prompt: str, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            return call_llm(prompt)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # Exponential backoff
            time.sleep(wait_time)
```

### Reranking Service

#### Reranker Types

##### 1. Cross-Encoder
```python
from sentence_transformers import CrossEncoder

model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def rerank_cross_encoder(query: str, chunks: List[str]) -> List[Tuple[str, float]]:
    pairs = [(query, chunk) for chunk in chunks]
    scores = model.predict(pairs)
    return sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
```

##### 2. Cohere Rerank
```python
import cohere

co = cohere.Client(api_key=settings.COHERE_API_KEY)

def rerank_cohere(query: str, chunks: List[str]) -> List[str]:
    results = co.rerank(
        query=query,
        documents=chunks,
        top_n=5,
        model='rerank-english-v2.0'
    )
    return [chunks[r.index] for r in results]
```

##### 3. BGE Reranker
```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model = AutoModelForSequenceClassification.from_pretrained('BAAI/bge-reranker-base')
tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-reranker-base')

def rerank_bge(query: str, chunks: List[str]) -> List[str]:
    pairs = [[query, chunk] for chunk in chunks]
    inputs = tokenizer(pairs, padding=True, truncation=True, return_tensors='pt')
    scores = model(**inputs).logits.squeeze()
    return [chunk for _, chunk in sorted(zip(scores, chunks), reverse=True)]
```

##### 4. LLM Reranking
```python
def rerank_llm(query: str, chunks: List[str]) -> List[str]:
    prompt = f"""
    Query: {query}
    
    Rank these passages by relevance (1 = most relevant):
    {format_chunks(chunks)}
    """
    response = llm_service.generate(prompt)
    return parse_ranked_chunks(response)
```

#### API

```python
from src.rag_service.infrastructure.reranking_service import get_reranking_service

reranking_service = get_reranking_service()

# Check availability
if reranking_service.is_available():
    # Get available types
    types = reranking_service.get_available_types()
    
    # Rerank results
    reranked = reranking_service.rerank(
        query="What is RAG?",
        chunks=retrieved_chunks,
        reranker_type="cross-encoder",
        top_k=5
    )
```

### Prompt Templates

#### Template System

```python
# prompt_templates.py

RAG_PROMPT_TEMPLATE = """
You are a helpful AI assistant. Answer the question based on the provided context.

Context:
{context}

Question: {question}

Answer:
"""

QUERY_EXPANSION_TEMPLATE = """
Generate 3 alternative phrasings for the following query:

Query: {query}

Alternative phrasings:
1.
2.
3.
"""

RERANKING_TEMPLATE = """
Query: {query}

Rank these passages by relevance to the query:

{passages}

Ranking (most to least relevant):
"""
```

#### Usage

```python
from src.rag_service.infrastructure.prompt_templates import RAG_PROMPT_TEMPLATE

prompt = RAG_PROMPT_TEMPLATE.format(
    context=context,
    question=question
)

response = llm_service.generate(prompt)
```

### Multi-Language Service

```python
from src.rag_service.application.multilang_service import detect_language

# Detect query language
language = detect_language("What is RAG?")  # Returns: "en"
language = detect_language("¿Qué es RAG?")  # Returns: "es"

# Language-specific processing
if language == "es":
    prompt = SPANISH_PROMPT_TEMPLATE.format(...)
else:
    prompt = ENGLISH_PROMPT_TEMPLATE.format(...)
```

## Configuration

### Environment Variables

```python
# LLM Configuration
OPENROUTER_API_KEY: str = ""
OPENROUTER_MODEL: str = "mistralai/mistral-7b-instruct"
OPENAI_API_KEY: str = ""
GOOGLE_API_KEY: str = ""
COHERE_API_KEY: str = ""

# Feature Flags
ENABLE_QUERY_EXPANSION: bool = True
ENABLE_RERANKING: bool = True

# Query Expansion
QUERY_EXPANSION_STRATEGY: str = "hybrid"

# Reranking
RERANKING_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

## Usage Examples

### Query Expansion

```python
from src.rag_service.application.query_expansion_service import get_expansion_service

service = get_expansion_service()

# Expand with default strategy
expanded = service.expand_query("What is RAG?")

# Expand with specific strategy
expanded = service.expand_query(
    query="What is RAG?",
    strategy="llm"
)

print(expanded)
# Output: [
#   "What is RAG?",
#   "What is retrieval augmented generation?",
#   "Explain RAG in AI",
#   "How does RAG work?"
# ]
```

### LLM Generation

```python
from src.rag_service.infrastructure.llm_service import generate_response

response = generate_response(
    prompt="What is RAG?",
    context=retrieved_context,
    model="mistralai/mistral-7b-instruct"
)

print(response)
# Output: {
#   "content": "RAG stands for Retrieval-Augmented Generation...",
#   "model": "mistralai/mistral-7b-instruct",
#   "tokens": {"prompt": 100, "completion": 50}
# }
```

### Reranking

```python
from src.rag_service.infrastructure.reranking_service import get_reranking_service

service = get_reranking_service()

reranked = service.rerank(
    query="What is RAG?",
    chunks=retrieved_chunks,
    reranker_type="cross-encoder",
    top_k=5
)

for i, chunk in enumerate(reranked, 1):
    print(f"{i}. {chunk.chunk_text[:100]}...")
```

## Performance Optimization

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def expand_query_cached(query: str, strategy: str) -> List[str]:
    return expand_query(query, strategy)
```

### Batch Processing

```python
# Batch reranking
def rerank_batch(queries: List[str], chunks: List[List[str]]):
    pairs = [(q, c) for q, chunk_list in zip(queries, chunks) for c in chunk_list]
    scores = model.predict(pairs)
    # Process scores...
```

### Async Operations

```python
import asyncio

async def expand_and_retrieve(query: str):
    expansion_task = asyncio.create_task(expand_query(query))
    embedding_task = asyncio.create_task(generate_embedding(query))
    
    expanded, embedding = await asyncio.gather(
        expansion_task,
        embedding_task
    )
    return expanded, embedding
```

## Error Handling

### LLM Errors

```python
try:
    response = call_llm(prompt)
except TimeoutError:
    logger.error("LLM request timed out")
    response = fallback_response()
except APIError as e:
    logger.error(f"LLM API error: {e}")
    response = fallback_response()
```

### Reranking Errors

```python
try:
    reranked = rerank(query, chunks)
except Exception as e:
    logger.warning(f"Reranking failed: {e}, using original order")
    reranked = chunks  # Fallback to original order
```

## Monitoring

### Metrics

```python
# Track LLM usage
logger.info(f"LLM tokens: {prompt_tokens + completion_tokens}")

# Track expansion effectiveness
logger.info(f"Expanded {len(original)} to {len(expanded)} queries")

# Track reranking impact
logger.info(f"Reranking changed order: {order_changed}")
```

## Testing

### Unit Tests

```bash
pytest tests/rag_service/test_query_expansion.py
pytest tests/rag_service/test_reranking.py
pytest tests/rag_service/test_llm_service.py
```

### Integration Tests

```bash
pytest tests/integration/test_rag_pipeline.py
```

## Future Enhancements

- [ ] Custom fine-tuned models
- [ ] Advanced prompt engineering
- [ ] Multi-turn conversation context
- [ ] Streaming LLM responses
- [ ] Custom reranking models
- [ ] A/B testing for strategies
- [ ] Advanced caching (Redis)
- [ ] Cost optimization

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md)
- [Chat Service](../chat_service/README.md)
- [Vector Service](../vector_service/README.md)

---

**Service Version**: 1.0  
**Last Updated**: February 2026
