"""Application configuration.

Reads settings from environment variables / a local .env file via
pydantic-settings. This keeps environment-specific values (API URLs,
model names) out of the source code.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ollama exposes an OpenAI-compatible API at /v1.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:7b-instruct"

    # Time in seconds to wait for the LLM to respond.
    llm_timeout_seconds: float = 60.0

    # How many times to retry a transient LLM failure (network blip, 5xx).
    llm_max_retries: int = 2

    # Lower temperature -> more deterministic output, which we want
    # for structured extraction.
    llm_temperature: float = 0.0

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    lru_cache means the .env file is only parsed once per process,
    not on every request.
    """
    return Settings()