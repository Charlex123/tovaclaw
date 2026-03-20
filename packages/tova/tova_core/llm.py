"""
LLM factory — builds the right ChatModel based on the configured provider.

Supported providers:
  - anthropic: Claude (claude-opus-4-6, claude-sonnet-4-6, etc.)
  - openai: GPT (gpt-4o, gpt-4-turbo, etc.)
  - google: Gemini (gemini-2.0-flash, gemini-2.5-pro, etc.)
  - local: Any OpenAI-compatible local server (Ollama, vLLM, LM Studio)
"""

import logging
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from tova_core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def build_llm(temperature: float | None = None) -> BaseChatModel:
    """Build a ChatModel from the configured provider and model name."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    model = settings.agent_model
    temp = temperature if temperature is not None else settings.agent_temperature
    max_tokens = settings.agent_max_tokens

    logger.info(f"Building LLM: provider={provider}, model={model}")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when llm_provider=anthropic")
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            max_tokens=max_tokens,
            temperature=temp,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when llm_provider=openai")
        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            max_tokens=max_tokens,
            temperature=temp,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when llm_provider=google")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            max_output_tokens=max_tokens,
            temperature=temp,
        )

    elif provider == "local":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            base_url=settings.local_llm_base_url,
            api_key="not-needed",
            max_tokens=max_tokens,
            temperature=temp,
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            f"Supported: anthropic, openai, google, local"
        )
