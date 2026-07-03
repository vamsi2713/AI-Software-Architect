"""
Centralized application configuration.

Every infrastructure client (Neo4j, Qdrant, Postgres) needs credentials.
Instead of each module calling os.getenv() directly, we define one
Settings object that reads from .env, validates types at import time
(fail fast), and gets injected into clients via dependency injection.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "ai-software-architect"
    environment: str = "development"
    log_level: str = "INFO"

    # Neo4j (AuraDB)
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str

    # Qdrant Cloud
    qdrant_url: str
    qdrant_api_key: str

    # Postgres
    postgres_dsn: str

    # LLM providers - optional, at least one should be set eventually
    gemini_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton - Settings() only gets constructed once
    per process, not re-parsed from environment on every request."""
    return Settings()