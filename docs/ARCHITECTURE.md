# Architecture Overview

## Table of Contents
- [System Overview](#system-overview)
- [Architecture Pattern](#architecture-pattern)
- [System Architecture Diagram](#system-architecture-diagram)
- [Service Components](#service-components)
- [Data Flow](#data-flow)
- [RAG Pipeline](#rag-pipeline)
- [Authentication Flow](#authentication-flow)
- [Database Schema](#database-schema)
- [Technology Stack](#technology-stack)

---

## System Overview

The **LLM User Service** is a production-grade **Retrieval-Augmented Generation (RAG)** system built as a **Modular Monolith**. It provides intelligent question-answering capabilities by combining vector search, hybrid retrieval, and large language models.

### Key Capabilities
- **Semantic Search** - Vector-based similarity search using pgvector
- **Hybrid Retrieval** - Combines dense (vector) and sparse (BM25) search
- **Query Expansion** - Enhances queries for better retrieval
- **Reranking** - Improves result relevance using cross-encoders
- **Multi-LLM Support** - OpenRouter, OpenAI, Google Generative AI
- **Session Management** - Persistent chat sessions with history
- **Document Ingestion** - Automated document processing and embedding

---

## Architecture Pattern

### Modular Monolith

The system follows a **Modular Monolith** architecture pattern, organizing code into feature-based service modules with clear boundaries and responsibilities.

#### Benefits
- **Independent Development** - Teams can work on different services independently
- **Clear Boundaries** - Well-defined interfaces between modules
- **Easier Testing** - Services can be tested in isolation
- **Deployment Simplicity** - Single deployment unit (vs microservices)
- **Shared Resources** - Efficient use of database connections and models

#### Domain-Driven Design (DDD) Layers

Each service follows a **layered architecture** inspired by DDD:

```
┌─────────────────────────────────────┐
│         API Layer (Routes)          │  ← FastAPI endpoints
├─────────────────────────────────────┤
│    Application Layer (Services)     │  ← Business logic orchestration
├─────────────────────────────────────┤
│      Domain Layer (Entities)        │  ← Core business models
├─────────────────────────────────────┤
│  Infrastructure Layer (Adapters)    │  ← External integrations
└─────────────────────────────────────┘
```

---

## System Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        UI[Web UI<br/>HTML/JS/CSS]
        API_CLIENT[External API Clients]
    end

    subgraph "API Gateway Layer"
        FASTAPI[FastAPI Application<br/>main.py]
    end

    subgraph "Service Layer - Feature Modules"
        ADMIN[Admin Service<br/>System Management]
        AUTH[Auth Service<br/>Authentication]
        CHAT[Chat Service<br/>RAG Pipeline]
        USER[User Service<br/>User Management]
        INGESTION[Ingestion Service<br/>Document Processing]
        RAG[RAG Service<br/>Query Enhancement]
        VECTOR[Vector Service<br/>Search Operations]
        DB_SVC[DB Service<br/>Data Access]
    end

    subgraph "Shared Components"
        CONFIG[Configuration]
        LOGGING[Logging]
        EXCEPTIONS[Exception Handling]
        SCHEMAS[Shared Schemas]
        MONITORING[Monitoring]
    end

    subgraph "Infrastructure Layer"
        LLM[LLM Service<br/>OpenRouter/OpenAI]
        EMBEDDING[Embedding Models<br/>SentenceTransformers]
        RERANKER[Reranking Service<br/>Cross-Encoder/Cohere]
        SEARCH[Search Service<br/>BM25]
    end

    subgraph "Data Layer"
        POSTGRES[(PostgreSQL<br/>+ pgvector)]
    end

    subgraph "External Services"
        OPENROUTER[OpenRouter API]
        COHERE[Cohere API]
        OPENAI[OpenAI API]
        GOOGLE[Google AI API]
    end

    UI --> FASTAPI
    API_CLIENT --> FASTAPI
    
    FASTAPI --> ADMIN
    FASTAPI --> AUTH
    FASTAPI --> CHAT
    FASTAPI --> USER
    FASTAPI --> INGESTION
    
    ADMIN --> DB_SVC
    AUTH --> DB_SVC
    CHAT --> RAG
    CHAT --> VECTOR
    CHAT --> DB_SVC
    USER --> DB_SVC
    INGESTION --> DB_SVC
    INGESTION --> EMBEDDING
    
    RAG --> LLM
    RAG --> RERANKER
    VECTOR --> SEARCH
    VECTOR --> EMBEDDING
    
    DB_SVC --> POSTGRES
    
    LLM --> OPENROUTER
    LLM --> OPENAI
    LLM --> GOOGLE
    RERANKER --> COHERE
    
    ADMIN -.-> CONFIG
    AUTH -.-> CONFIG
    CHAT -.-> CONFIG
    USER -.-> CONFIG
    INGESTION -.-> CONFIG
    RAG -.-> CONFIG
    VECTOR -.-> CONFIG
    
    ADMIN -.-> LOGGING
    AUTH -.-> LOGGING
    CHAT -.-> LOGGING
    USER -.-> LOGGING
    INGESTION -.-> LOGGING
    RAG -.-> LOGGING
    VECTOR -.-> LOGGING
    
    style FASTAPI fill:#4CAF50,stroke:#2E7D32,color:#fff
    style CHAT fill:#2196F3,stroke:#1565C0,color:#fff
    style RAG fill:#2196F3,stroke:#1565C0,color:#fff
    style VECTOR fill:#2196F3,stroke:#1565C0,color:#fff
    style POSTGRES fill:#FF9800,stroke:#E65100,color:#fff
    style LLM fill:#9C27B0,stroke:#6A1B9A,color:#fff
```

---

## Service Components

### 1. Admin Service
**Purpose**: System administration and monitoring

**Responsibilities**:
- Health checks and diagnostics
- System metrics and monitoring
- Session management
- Resource information
- Response logging

**Key Endpoints**:
- `GET /api/health` - System health status
- `GET /api/diagnostics` - Detailed diagnostics
- `GET /api/monitoring/metrics` - Performance metrics
- `GET /api/sessions` - Session management

---

### 2. Auth Service
**Purpose**: Authentication and authorization

**Responsibilities**:
- User authentication (JWT)
- User registration
- Token management
- Password hashing (bcrypt)

**Key Endpoints**:
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration

**Architecture**:
```
auth_service/
├── api/          # FastAPI routes
├── application/  # Auth business logic
├── domain/       # User entities
└── infrastructure/ # JWT, password hashing
```

---

### 3. Chat Service
**Purpose**: Conversational interface and RAG pipeline orchestration

**Responsibilities**:
- Process user queries
- Orchestrate RAG pipeline
- Manage chat sessions
- Return formatted responses

**Key Endpoints**:
- `POST /api/chat` - Chat endpoint (simplified)
- `POST /api/query` - Full RAG pipeline

**Architecture**:
```
chat_service/
├── api/          # Chat routes
├── application/  # ChatService (orchestrator)
├── domain/       # Chat entities
└── infrastructure/ # External integrations
```

---

### 4. DB Service
**Purpose**: Database access and ORM models

**Responsibilities**:
- SQLAlchemy models
- Database connection management
- CRUD operations
- Database migrations

**Key Components**:
- `models.py` - SQLAlchemy ORM models
- `database.py` - Connection setup
- `crud.py` - CRUD operations
- `migrations/` - Database migrations

**Models**:
- `UserQuery` - User questions
- `QueryResponse` - LLM responses
- `DocumentChunk` - Vector embeddings
- `ChatSession` - Chat sessions
- `ChatMessage` - Chat messages
- `Subscription` - User subscriptions
- `FileUpload` - Uploaded files

---

### 5. Ingestion Service
**Purpose**: Document processing and embedding generation

**Responsibilities**:
- Document upload handling
- Text extraction and cleaning
- Chunk generation
- Embedding creation
- Vector storage

**Key Endpoints**:
- `POST /api/ingest` - Upload and process documents
- `GET /api/documents` - List documents
- `DELETE /api/documents/{id}` - Delete document

**Architecture**:
```
ingestion_service/
├── api/          # Ingestion routes
├── application/  # Document processing
│   ├── cleaning/ # Text cleaning
│   └── folder_service.py
├── domain/       # Document entities
└── infrastructure/ # File storage
```

---

### 6. RAG Service
**Purpose**: Query enhancement and LLM orchestration

**Responsibilities**:
- Query expansion (multiple strategies)
- LLM integration (OpenRouter, OpenAI, Google)
- Prompt template management
- Response reranking
- Multi-language support

**Key Components**:
- `query_expansion_service.py` - Query enhancement
- `llm_service.py` - LLM orchestration
- `reranking_service.py` - Result reranking
- `prompt_templates.py` - Prompt management
- `multilang_service.py` - Language detection

**Query Expansion Strategies**:
- **Static** - Predefined expansions
- **LLM** - LLM-generated expansions
- **Hybrid** - Combines multiple strategies
- **Module-wise** - Domain-specific expansions
- **Token-optimized** - Efficient token usage

**Reranking Types**:
- **Cross-Encoder** - Transformer-based reranking
- **Cohere** - Cohere Rerank API
- **BGE** - BGE reranker model
- **LLM** - LLM-based reranking

---

### 7. User Service
**Purpose**: User profile and preference management

**Responsibilities**:
- User profile CRUD
- User preferences
- User settings

**Key Endpoints**:
- `GET /api/user/profile` - Get user profile
- `PUT /api/user/profile` - Update profile
- `GET /api/user/preferences` - Get preferences

---

### 8. Vector Service
**Purpose**: Vector search and hybrid retrieval

**Responsibilities**:
- Dense vector search (pgvector)
- Sparse search (BM25)
- Hybrid retrieval (combines both)
- Search service initialization

**Key Components**:
- `search_service.py` - BM25 search
- `hybrid_retrieval.py` - Hybrid search

**Search Methods**:
```mermaid
graph LR
    QUERY[User Query] --> DENSE[Dense Search<br/>pgvector]
    QUERY --> SPARSE[Sparse Search<br/>BM25]
    DENSE --> HYBRID[Hybrid Merge<br/>RRF Algorithm]
    SPARSE --> HYBRID
    HYBRID --> RERANK[Reranking]
    RERANK --> RESULTS[Top K Results]
    
    style QUERY fill:#4CAF50,color:#fff
    style HYBRID fill:#2196F3,color:#fff
    style RESULTS fill:#FF9800,color:#fff
```

---

## Data Flow

### High-Level Request Flow

```mermaid
sequenceDiagram
    participant User
    participant FastAPI
    participant ChatService
    participant VectorService
    participant RAGService
    participant LLMService
    participant Database
    
    User->>FastAPI: POST /api/chat
    FastAPI->>ChatService: process_chat()
    
    ChatService->>Database: Save UserQuery
    
    alt Query Expansion Enabled
        ChatService->>RAGService: expand_query()
        RAGService-->>ChatService: expanded_queries
    end
    
    ChatService->>VectorService: retrieve_documents()
    
    alt Hybrid Retrieval
        VectorService->>Database: dense_search (pgvector)
        VectorService->>VectorService: sparse_search (BM25)
        VectorService->>VectorService: merge_results (RRF)
    else Dense Only
        VectorService->>Database: dense_search (pgvector)
    end
    
    VectorService-->>ChatService: retrieved_chunks
    
    alt Reranking Enabled
        ChatService->>RAGService: rerank_results()
        RAGService-->>ChatService: reranked_chunks
    end
    
    ChatService->>RAGService: build_prompt()
    ChatService->>LLMService: generate_response()
    LLMService-->>ChatService: llm_response
    
    ChatService->>Database: Save QueryResponse
    ChatService->>Database: Save ChatMessage
    
    ChatService-->>FastAPI: response_data
    FastAPI-->>User: JSON Response
```

---

## RAG Pipeline

### Detailed RAG Pipeline Flow

```mermaid
flowchart TD
    START([User Query]) --> VALIDATE{Valid Query?}
    VALIDATE -->|No| ERROR[Return Error]
    VALIDATE -->|Yes| SESSION[Create/Get Session]
    
    SESSION --> SAVE_QUERY[Save to user_queries]
    SAVE_QUERY --> EXPAND{Query Expansion<br/>Enabled?}
    
    EXPAND -->|Yes| EXPANSION[Query Expansion Service]
    EXPANSION --> STRATEGY{Strategy}
    STRATEGY -->|Static| STATIC[Predefined Terms]
    STRATEGY -->|LLM| LLM_EXPAND[LLM Generation]
    STRATEGY -->|Hybrid| HYBRID_EXPAND[Multiple Strategies]
    STATIC --> EXPANDED[Expanded Queries]
    LLM_EXPAND --> EXPANDED
    HYBRID_EXPAND --> EXPANDED
    
    EXPAND -->|No| ORIGINAL[Original Query]
    EXPANDED --> EMBED
    ORIGINAL --> EMBED
    
    EMBED[Generate Embeddings] --> RETRIEVAL{Retrieval Mode}
    
    RETRIEVAL -->|Dense| DENSE[pgvector Search]
    RETRIEVAL -->|Hybrid| HYBRID_RET[Hybrid Retrieval]
    
    HYBRID_RET --> DENSE_H[Dense Search]
    HYBRID_RET --> SPARSE[BM25 Search]
    DENSE_H --> RRF[Reciprocal Rank Fusion]
    SPARSE --> RRF
    RRF --> CHUNKS
    
    DENSE --> CHUNKS[Retrieved Chunks]
    
    CHUNKS --> RERANK{Reranking<br/>Enabled?}
    RERANK -->|Yes| RERANK_SVC[Reranking Service]
    RERANK_SVC --> RERANK_TYPE{Type}
    RERANK_TYPE -->|Cross-Encoder| CE[Cross-Encoder Model]
    RERANK_TYPE -->|Cohere| COHERE[Cohere API]
    RERANK_TYPE -->|BGE| BGE[BGE Model]
    RERANK_TYPE -->|LLM| LLM_RERANK[LLM Reranking]
    
    CE --> RANKED
    COHERE --> RANKED
    BGE --> RANKED
    LLM_RERANK --> RANKED
    
    RERANK -->|No| RANKED[Ranked Chunks]
    
    RANKED --> CONTEXT[Build Context]
    CONTEXT --> PROMPT[Build Prompt]
    PROMPT --> LLM[LLM Generation]
    
    LLM --> OPENROUTER{LLM Provider}
    OPENROUTER -->|OpenRouter| OR[OpenRouter API]
    OPENROUTER -->|OpenAI| OAI[OpenAI API]
    OPENROUTER -->|Google| GOOGLE[Google AI API]
    
    OR --> RESPONSE
    OAI --> RESPONSE
    GOOGLE --> RESPONSE
    
    RESPONSE[LLM Response] --> SAVE_RESP[Save to query_responses]
    SAVE_RESP --> SAVE_MSG[Save to chat_messages]
    SAVE_MSG --> RETURN([Return Response])
    
    style START fill:#4CAF50,color:#fff
    style EXPANSION fill:#2196F3,color:#fff
    style HYBRID_RET fill:#2196F3,color:#fff
    style RERANK_SVC fill:#9C27B0,color:#fff
    style LLM fill:#FF9800,color:#fff
    style RETURN fill:#4CAF50,color:#fff
```

### Pipeline Stages

#### 1. Query Processing
- Validate input
- Create/retrieve session
- Save query to database

#### 2. Query Enhancement (Optional)
- **Query Expansion** - Generate additional query variations
- **Language Detection** - Identify query language
- **Tagging** - Extract key terms

#### 3. Retrieval
- **Embedding Generation** - Convert query to vector
- **Dense Search** - Semantic similarity (pgvector)
- **Sparse Search** - Keyword matching (BM25)
- **Hybrid Merge** - Combine results using RRF

#### 4. Reranking (Optional)
- **Cross-Encoder** - Deep semantic matching
- **Cohere Rerank** - API-based reranking
- **BGE Reranker** - Efficient reranking
- **LLM Reranking** - LLM-based relevance

#### 5. Response Generation
- **Context Building** - Format retrieved chunks
- **Prompt Construction** - Build LLM prompt
- **LLM Call** - Generate response
- **Post-processing** - Format and validate

#### 6. Persistence
- Save response to database
- Link to chat session
- Update session metadata

---

## Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant AuthAPI
    participant AuthService
    participant Database
    
    User->>Frontend: Enter credentials
    Frontend->>AuthAPI: POST /api/auth/login
    AuthAPI->>AuthService: authenticate()
    AuthService->>Database: Query user
    Database-->>AuthService: User record
    AuthService->>AuthService: Verify password (bcrypt)
    
    alt Valid Credentials
        AuthService->>AuthService: Generate JWT token
        AuthService-->>AuthAPI: Token + User data
        AuthAPI-->>Frontend: 200 OK + JWT
        Frontend->>Frontend: Store JWT
        Frontend-->>User: Login successful
    else Invalid Credentials
        AuthService-->>AuthAPI: Authentication failed
        AuthAPI-->>Frontend: 401 Unauthorized
        Frontend-->>User: Login failed
    end
    
    Note over Frontend,AuthAPI: Subsequent Requests
    Frontend->>AuthAPI: Request + JWT Header
    AuthAPI->>AuthService: Validate JWT
    AuthService-->>AuthAPI: User context
    AuthAPI->>AuthAPI: Process request
    AuthAPI-->>Frontend: Response
```

### JWT Token Structure
```json
{
  "sub": "user_id",
  "exp": 1234567890,
  "iat": 1234567890,
  "type": "access"
}
```

---

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ CHAT_SESSION : creates
    USER ||--o{ SUBSCRIPTION : has
    USER ||--o{ FILE_UPLOAD : uploads
    
    CHAT_SESSION ||--o{ CHAT_MESSAGE : contains
    CHAT_SESSION ||--o{ USER_QUERY : has
    
    USER_QUERY ||--|| QUERY_RESPONSE : generates
    
    QUERY_RESPONSE ||--o{ DOCUMENT_CHUNK : references
    
    CHAT_MESSAGE }|--|| USER_QUERY : links
    CHAT_MESSAGE }|--|| QUERY_RESPONSE : links
    
    USER {
        string id PK
        string email
        string hashed_password
        datetime created_at
        datetime updated_at
    }
    
    CHAT_SESSION {
        string session_id PK
        string user_id FK
        boolean is_temporary
        datetime created_at
        datetime updated_at
    }
    
    USER_QUERY {
        int id PK
        string query_text
        string session_id FK
        string language
        datetime created_at
    }
    
    QUERY_RESPONSE {
        int id PK
        int query_id FK
        string response_text
        array retrieved_context_ids
        string llm_model
        jsonb response_metadata
        float latency_ms
        datetime created_at
    }
    
    DOCUMENT_CHUNK {
        int id PK
        string chunk_text
        vector embedding
        string source_name
        string file_path
        int chunk_index
        jsonb metadata
        datetime created_at
    }
    
    CHAT_MESSAGE {
        int id PK
        string session_id FK
        int query_id FK
        int response_id FK
        boolean is_favourite
        array tags
        string feedback
        datetime created_at
    }
    
    SUBSCRIPTION {
        int id PK
        string user_id FK
        string plan_type
        datetime start_date
        datetime end_date
        boolean is_active
    }
    
    FILE_UPLOAD {
        int id PK
        string user_id FK
        string filename
        string file_path
        string status
        datetime uploaded_at
    }
```

### Key Tables

#### user_queries
Stores all user questions
- `id` - Primary key
- `query_text` - The question
- `session_id` - Links to chat session
- `language` - Detected language
- `created_at` - Timestamp

#### query_responses
Stores LLM responses
- `id` - Primary key
- `query_id` - Links to user query
- `response_text` - LLM answer
- `retrieved_context_ids` - Array of chunk IDs
- `llm_model` - Model used
- `response_metadata` - Token counts, etc.
- `latency_ms` - Response time

#### document_chunks
Stores embedded document chunks
- `id` - Primary key
- `chunk_text` - Text content
- `embedding` - Vector (384-dim)
- `source_name` - Document name
- `file_path` - File location
- `chunk_index` - Position in document
- `metadata` - Additional info

#### chat_sessions
Manages chat sessions
- `session_id` - Primary key (UUID)
- `user_id` - User identifier
- `is_temporary` - Temporary session flag
- `created_at` - Creation time
- `updated_at` - Last activity

#### chat_messages
Links queries and responses to sessions
- `id` - Primary key
- `session_id` - Session reference
- `query_id` - Query reference
- `response_id` - Response reference
- `is_favourite` - User marked favorite
- `tags` - User tags
- `feedback` - User feedback

---

## Technology Stack

For detailed technology stack information, see [Tech Stack Documentation](tech_stack.md).

### Core Technologies
- **FastAPI** - Web framework
- **PostgreSQL + pgvector** - Database + vector search
- **SQLAlchemy** - ORM
- **Sentence Transformers** - Embeddings
- **PyTorch** - ML framework
- **OpenRouter** - LLM gateway

---

## Deployment Architecture

### Production Deployment

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/Traefik]
    end
    
    subgraph "Application Tier"
        APP1[FastAPI Instance 1]
        APP2[FastAPI Instance 2]
        APP3[FastAPI Instance N]
    end
    
    subgraph "Database Tier"
        PRIMARY[(PostgreSQL Primary<br/>+ pgvector)]
        REPLICA[(PostgreSQL Replica<br/>Read-only)]
    end
    
    subgraph "Cache Layer"
        REDIS[(Redis Cache)]
    end
    
    subgraph "External Services"
        LLM_EXT[LLM APIs]
    end
    
    LB --> APP1
    LB --> APP2
    LB --> APP3
    
    APP1 --> PRIMARY
    APP2 --> PRIMARY
    APP3 --> PRIMARY
    
    APP1 --> REPLICA
    APP2 --> REPLICA
    APP3 --> REPLICA
    
    APP1 --> REDIS
    APP2 --> REDIS
    APP3 --> REDIS
    
    APP1 --> LLM_EXT
    APP2 --> LLM_EXT
    APP3 --> LLM_EXT
    
    PRIMARY -.replication.-> REPLICA
    
    style LB fill:#4CAF50,color:#fff
    style PRIMARY fill:#FF9800,color:#fff
    style REDIS fill:#F44336,color:#fff
```

### Scaling Considerations

#### Horizontal Scaling
- **Stateless Application** - Multiple FastAPI instances
- **Load Balancing** - Distribute requests
- **Database Replication** - Read replicas for queries

#### Vertical Scaling
- **Database Resources** - Increase PostgreSQL resources
- **Model Caching** - Cache embeddings and models
- **Connection Pooling** - Efficient database connections

#### Caching Strategy
- **Response Cache** - Cache frequent queries
- **Embedding Cache** - Cache generated embeddings
- **Model Cache** - Cache loaded models in memory

---

## Security Considerations

### Authentication & Authorization
- **JWT Tokens** - Secure token-based auth
- **Password Hashing** - bcrypt with salt
- **Token Expiration** - 8-day default expiration

### Data Security
- **SQL Injection Protection** - SQLAlchemy ORM
- **Input Validation** - Pydantic schemas
- **CORS Configuration** - Configurable origins

### API Security
- **Rate Limiting** - Prevent abuse (recommended)
- **HTTPS/TLS** - Encrypted communication
- **API Key Management** - Secure key storage

---

## Monitoring & Observability

### Health Checks
- `GET /health` - System health status
- `GET /api/diagnostics` - Detailed diagnostics

### Metrics
- Request count and latency
- Token usage (LLM)
- Cache hit rates
- Database query performance

### Logging
- Structured logging (JSON)
- Log levels (DEBUG, INFO, WARNING, ERROR)
- Request/response logging
- Error tracking

---

## Performance Optimization

### Database Optimization
- **Indexes** - On frequently queried columns
- **Connection Pooling** - Reuse connections
- **Query Optimization** - Efficient SQL queries

### Vector Search Optimization
- **HNSW Indexes** - Fast approximate search
- **Batch Processing** - Process multiple queries
- **Dimension Reduction** - Smaller embeddings

### LLM Optimization
- **Prompt Caching** - Cache common prompts
- **Token Optimization** - Minimize token usage
- **Retry Logic** - Handle API failures gracefully

---

## Future Enhancements

### Planned Features
- [ ] Multi-tenancy support
- [ ] Advanced analytics dashboard
- [ ] Custom model fine-tuning
- [ ] Real-time collaboration
- [ ] Advanced caching strategies
- [ ] GraphQL API support
- [ ] Webhook integrations
- [ ] Advanced role-based access control

### Scalability Roadmap
- [ ] Microservices migration path
- [ ] Event-driven architecture
- [ ] Message queue integration (RabbitMQ/Kafka)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Service mesh (Istio)

---

## References

- [Tech Stack Documentation](tech_stack.md)
- [API Documentation](api_documentation.md)
- [Deployment Guide](deployment_guide.md)
- Service READMEs:
  - [Admin Service](../src/admin_service/README.md)
  - [Auth Service](../src/auth_service/README.md)
  - [Chat Service](../src/chat_service/README.md)
  - [DB Service](../src/db_service/README.md)
  - [Ingestion Service](../src/ingestion_service/README.md)
  - [RAG Service](../src/rag_service/README.md)
  - [User Service](../src/user_service/README.md)
  - [Vector Service](../src/vector_service/README.md)

---

**Document Version**: 1.0  
**Last Updated**: February 2026  
**Maintained By**: Development Team
