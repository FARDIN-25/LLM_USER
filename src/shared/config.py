import logging
import os
from functools import lru_cache
from typing import List, Optional, Union, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl, validator, field_validator

class Settings(BaseSettings):
    """
    Application Settings
    
    Reads configuration from environment variables and .env file.
    Provides type safety and default values.
    """
    model_config = SettingsConfigDict(
        env_file=(".env", "src/.env"), 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Project Info
    PROJECT_NAME: str = "LLM RAG Enterprise"
    APP_ENV: Literal["development", "production", "test"] = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = Field("secret", description="JWT Secret Key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    DEBUG: bool = False
    LOG_LLM_USAGE: bool = True
    
    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL Connection String")
    PAGE_INDEX_DATABASE_URL: str = Field(
        "",
        description="Optional Postgres URL for PageIndex jobs table (e.g., fts_testing.page_index_jobs)",
    )
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 4
    DB_POOL_PRE_PING: bool = True
    # LLM (OpenRouter)
    OPENROUTER_API_KEY: str = Field("", description="OpenRouter API Key")
    OPENROUTER_MODEL: str = "mistralai/ministral-8b-2512"
    # LLM (MISTRAL)
    MISTRAL_API_KEY: str = Field("", description="MISTRAL API Key")
    MISTRAL_MODEL: str = "ministral-8b-2512"
    REWRITE_MODEL: str = Field("mistralai/ministral-8b-2512", description="Model for rewriting follow-up questions")
    REWRITE_HISTORY_TURNS: int = Field(100, description="Number of previous chat turns to use for rewriting")
    REWRITE_CONTENT_CHARS: int = Field(500, description="Max characters per history message to include in rewrite prompt")
    MISTRAL_ENABLED: bool = True

    
    # Cohere
    COHERE_API_KEY: str = Field("", description="Cohere API Key")
    
    # Search / Retrieval
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EXPECTED_EMBEDDING_DIM: int = 384
    MAX_CONTEXT_CHARS: int = 6000

    QUERY_EXPANSION_STRATEGY: str = "hybrid"
    
    # Reranking
    RERANKING_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # Feature Flags
    ENABLE_HYBRID_SEARCH: bool = True
    ENABLE_RERANKING: bool = True
    ENABLE_QUERY_EXPANSION: bool = True
    
    # External Service URLs
    CLEANING_SERVICE_URL: str = "http://localhost:5000"
    INGESTION_SERVICE_URL: str = "http://localhost:8000"
    
    # Paths
    UPLOAD_DIR: str = "uploads"
    STATIC_DIR: str = "static"
    # Upload limits (configurable via env MAX_UPLOAD_SIZE_MB)
    MAX_UPLOAD_SIZE_MB: int = Field(10, ge=1, le=500, description="Max allowed file size in MB")
    
    # Cors
    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

@lru_cache()
def get_settings() -> Settings:
    """
    Creates and caches the settings object.
    Dependency injection friendly.
    """
    return Settings()

# Global settings instance for non-DI usage
settings = get_settings()
