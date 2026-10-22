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
    # 180s: the capstone box is CPU-only and qwen2.5:7b can need >1min per
    # generation (60s caused live /chat failures; retries x3 compounded it).
    llm_timeout_seconds: float = 180.0

    # How many times to retry a transient LLM failure (network blip, 5xx).
    llm_max_retries: int = 2

    # Lower temperature -> more deterministic output, which we want
    # for structured extraction.
    llm_temperature: float = 0.0

    # Knowledge Assistant Service (module4) - consumed over HTTP.
    kas_base_url: str = "http://localhost:8002"
    # /chunk embeds every sentence via Ollama, so a long transcript can take
    # well over 30s server-side; 120s covers realistic meeting sizes.
    kas_timeout_seconds: float = 120.0
    kas_max_retries: int = 2
    kas_search_top_k: int = 5

    # Transcripts longer than this many characters are chunked via the KAS
    # /chunk endpoint before LLM analysis (context-window guard).
    chunk_threshold_chars: int = 20_000

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