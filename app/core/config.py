"""
Core configuration — loads environment variables via Pydantic Settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Ollama (local LLM) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # --- Instagram / Meta ---
    insta_verify_token: str = ""
    insta_access_token: str = ""
    insta_account_id: str = ""

    # --- Database ---
    database_url: str = "sqlite:///./kyana.db"

    # --- App ---
    app_name: str = "Kyana"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
