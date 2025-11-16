"""Configuration settings for the QA system."""

import logging
from functools import lru_cache
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # External APIs
    pinecone_api_key: str
    pinecone_index_name: str = "aurora"
    pinecone_environment: str = "us-west-1"

    openrouter_api_key: str
    openrouter_model: str = "openai/gpt-4o-mini"

    huggingface_api_key: str
    hf_embedding_model: str = "BAAI/bge-large-en-v1.5"

    logfire_token: str = ""  # Optional - leave empty to disable Logfire

    # External API URLs
    external_api_url: str = "https://november7-730026606190.europe-west1.run.app"

    # Application Settings
    log_level: str = "INFO"
    environment: str = "development"

    # Retrieval Settings
    top_k_initial_retrieval: int = 100  # Increased to handle typos/format issues - more candidates
    top_k_after_reranking: int = 10  # Increased to give LLM more context for better matching
    embedding_batch_size: int = 100
    message_batch_size: int = 256

    # Background Job Settings
    indexing_enabled: bool = False  # Disabled by default - enable via POST /reindex to avoid OOM on startup
    indexing_batch_size: int = 256
    delta_refresh_hours: int = 12
    full_reindex_days: int = 7

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    logger.info("Loading settings from environment")
    return Settings()

