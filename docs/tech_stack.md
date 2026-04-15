# Tech Stack Documentation

## Overview
This document outlines the complete technology stack for the **LLM User Service** - a production-grade RAG (Retrieval-Augmented Generation) system built with modern Python tools.

---

## Backend Framework

### Core Web Framework
- **FastAPI** (≥0.104.0)
  - Modern, high-performance Python web framework
  - Automatic API documentation (OpenAPI/Swagger)
  - Built-in data validation with Pydantic
  - Async support for high concurrency

- **Uvicorn** (≥0.24.0)
  - ASGI server with standard extras
  - High-performance async server
  - WebSocket support

---

## Database & Vector Store

### Primary Database
- **PostgreSQL**
  - Relational database for structured data
  - ACID compliance for data integrity
  - Advanced querying capabilities

### Vector Database
- **pgvector**
  - PostgreSQL extension for vector similarity search
  - Enables semantic search capabilities
  - Stores and queries embeddings efficiently

### ORM & Database Tools
- **SQLAlchemy** (≥2.0.0)
  - Python SQL toolkit and ORM
  - Database abstraction layer
  - Connection pooling and session management

- **psycopg2-binary** (≥2.9.0)
  - PostgreSQL adapter for Python
  - Efficient database connectivity

---

## AI/ML & LLM Components

### Large Language Models
- **OpenRouter**
  - LLM API gateway
  - Default model: `mistralai/mistral-7b-instruct`
  - Provides access to multiple LLM providers

- **OpenAI** (≥1.0.0)
  - OpenAI API client
  - Support for GPT models

- **Google Generative AI** (≥0.3.0)
  - Google's Gemini and other AI models
  - Alternative LLM provider

### Embedding Models
- **Sentence Transformers** (≥2.2.0)
  - Default model: `all-MiniLM-L6-v2`
  - Embedding dimension: 384
  - Converts text to vector representations

### ML Frameworks
- **Transformers** (≥4.30.0)
  - Hugging Face transformers library
  - Access to pre-trained models
  - Model fine-tuning capabilities

- **PyTorch** (≥2.0.0)
  - Deep learning framework
  - GPU acceleration support
  - Model training and inference

### AI Services
- **Cohere** (≥4.0.0)
  - Reranking capabilities
  - Additional NLP features
  - Enterprise AI services

---

## RAG (Retrieval-Augmented Generation) Features

### Retrieval Methods
- **Hybrid Retrieval**
  - Combines dense (vector) and sparse (BM25) search
  - Improved retrieval accuracy
  - Configurable via `ENABLE_HYBRID_SEARCH` flag

- **BM25** (rank-bm25 ≥0.2.2)
  - Sparse retrieval algorithm
  - Keyword-based search
  - Complements vector search

### Query Enhancement
- **Query Expansion**
  - Multiple expansion strategies (hybrid, semantic, keyword)
  - Improves retrieval recall
  - Configurable via `ENABLE_QUERY_EXPANSION` flag

### Reranking
- **Cross-Encoder Reranking**
  - Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - Improves result relevance
  - Configurable via `ENABLE_RERANKING` flag

---

## Authentication & Security

### Authentication
- **python-jose[cryptography]** (≥3.3.0)
  - JWT (JSON Web Token) implementation
  - Secure token generation and validation
  - Cryptographic signing

### Password Security
- **passlib[bcrypt]** (≥1.7.4)
  - Password hashing with bcrypt
  - Secure password storage
  - Industry-standard encryption

---

## Configuration & Utilities

### Data Validation
- **Pydantic** (≥2.0.0)
  - Data validation using Python type hints
  - Settings management
  - Automatic data parsing

- **pydantic-settings** (≥2.0.0)
  - Environment-based configuration
  - Type-safe settings
  - `.env` file support

### Environment Management
- **python-dotenv** (≥1.0.0)
  - Loads environment variables from `.env` files
  - Development/production configuration separation

### HTTP Client
- **Requests** (≥2.31.0)
  - HTTP library for API calls
  - External service integration

### Validation
- **email-validator** (≥2.0.0)
  - Email address validation
  - RFC-compliant validation

---

## Frontend & Templates

### Template Engine
- **Jinja2** (≥3.1.2)
  - HTML template rendering
  - Dynamic content generation
  - Template inheritance

### File Handling
- **aiofiles** (≥23.2.1)
  - Async file I/O operations
  - Non-blocking file handling

- **python-multipart** (≥0.0.6)
  - File upload support
  - Multipart form data parsing

### Static Files
- HTML/CSS/JavaScript served via FastAPI's `StaticFiles`
- Dashboard UI for monitoring and interaction

---

## Architecture Pattern

### Modular Monolith
The application is organized into feature-based services:

#### Service Modules
- **`admin_service`** - Administrative functionality and management
- **`chat_service`** - Chat and query handling
- **`ingestion_service`** - Document ingestion and processing
- **`auth_service`** - Authentication and authorization
- **`user_service`** - User management and profiles
- **`vector_service`** - Vector search operations
- **`rag_service`** - RAG pipeline orchestration
- **`db_service`** - Database operations and models

#### Shared Components
- **`shared/config.py`** - Centralized configuration
- **`shared/logging.py`** - Logging setup
- **`shared/exceptions.py`** - Custom exception handling
- **`shared/schemas.py`** - Shared data models

---

## Configuration Settings

### Environment Variables
Key configuration options (defined in `src/shared/config.py`):

#### Project Settings
- `PROJECT_NAME` - Application name
- `APP_ENV` - Environment (development/production/test)
- `SECRET_KEY` - JWT secret key
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration (default: 8 days)

#### Database
- `DATABASE_URL` - PostgreSQL connection string
- `DB_POOL_SIZE` - Connection pool size (default: 5)
- `DB_MAX_OVERFLOW` - Max overflow connections (default: 10)

#### LLM Configuration
- `OPENROUTER_API_KEY` - OpenRouter API key
- `OPENROUTER_MODEL` - Model selection (default: mistral-7b-instruct)
- `COHERE_API_KEY` - Cohere API key

#### Embedding & Search
- `EMBEDDING_MODEL_NAME` - Embedding model (default: all-MiniLM-L6-v2)
- `EXPECTED_EMBEDDING_DIM` - Embedding dimension (default: 384)
- `MAX_CONTEXT_CHARS` - Max context length (default: 10,000)

#### Feature Flags
- `ENABLE_HYBRID_SEARCH` - Enable hybrid retrieval (default: true)
- `ENABLE_RERANKING` - Enable reranking (default: true)
- `ENABLE_QUERY_EXPANSION` - Enable query expansion (default: true)

---

## System Requirements

### Python Version
- Python 3.9+ (recommended: Python 3.10 or 3.11)

### Database Requirements
- PostgreSQL 12+ with pgvector extension

### Hardware Recommendations
- **CPU**: Multi-core processor (4+ cores recommended)
- **RAM**: 8GB minimum, 16GB+ recommended for ML models
- **Storage**: SSD recommended for database and model caching
- **GPU**: Optional but recommended for faster embedding/inference

---

## Deployment Considerations

### Production Checklist
- [ ] Set `APP_ENV=production`
- [ ] Configure secure `SECRET_KEY`
- [ ] Set up proper database connection pooling
- [ ] Enable HTTPS/TLS
- [ ] Configure CORS origins appropriately
- [ ] Set up monitoring and logging
- [ ] Configure backup strategies
- [ ] Implement rate limiting
- [ ] Set up health check endpoints

### Scalability Features
- Connection pooling for database efficiency
- Async operations for high concurrency
- Caching layer for response optimization
- Modular architecture for independent scaling

---

## Development Tools

### Package Management
- **pip** - Python package installer
- **requirements.txt** - Dependency specification

### Recommended Development Tools
- **Virtual Environment** - `venv` or `virtualenv`
- **Code Formatting** - `black`, `isort`
- **Linting** - `flake8`, `pylint`
- **Type Checking** - `mypy`

---

## API Documentation

### Auto-Generated Documentation
- **Swagger UI** - Available at `/docs`
- **ReDoc** - Available at `/redoc`
- **OpenAPI Schema** - Available at `/openapi.json`

---

## Monitoring & Observability

### Built-in Endpoints
- `/health` - Health check with detailed status
- `/api/history` - Query history and statistics
- `/api/metrics/performance` - Performance metrics
- `/monitor` - Performance monitoring dashboard

### Logging
- Structured logging with Python's `logging` module
- Configurable log levels
- Request/response logging
- Error tracking

---

## Version Information

**Current Version**: 0.2.0

**Last Updated**: February 2026

---

## Additional Resources

### Documentation
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy: https://www.sqlalchemy.org/
- Sentence Transformers: https://www.sbert.net/
- pgvector: https://github.com/pgvector/pgvector

### Support
For issues or questions, refer to the project repository or internal documentation.
