"""
Tova configuration — loads from .env file or environment variables.

Supports multiple LLM providers: anthropic, openai, google, local (Ollama/vLLM).
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class TovaSettings(BaseSettings):
    # ── LLM Provider ──────────────────────────────────────────
    # Supported: "anthropic", "openai", "google", "local"
    llm_provider: str = "anthropic"

    # Anthropic (Claude)
    anthropic_api_key: str = ""

    # OpenAI (GPT)
    openai_api_key: str = ""

    # Google (Gemini)
    google_api_key: str = ""

    # Local LLM (Ollama, vLLM, LM Studio, etc.)
    local_llm_base_url: str = "http://localhost:11434/v1"

    # Model name — provider-specific
    # Examples: claude-opus-4-6, gpt-4o, gemini-2.0-flash, llama3.3
    agent_model: str = "claude-sonnet-4-6"

    # ── Agent Config ──────────────────────────────────────────
    agent_max_iterations: int = 15
    agent_temperature: float = 0.3
    agent_max_tokens: int = 4096
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> TovaSettings:
    return TovaSettings()
