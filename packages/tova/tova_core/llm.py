"""
LLM factory — builds the right ChatModel based on the configured provider.

Supported providers:
  - anthropic: Claude (claude-opus-4-6, claude-sonnet-4-6, etc.)
  - openai: GPT (gpt-4o, gpt-4-turbo, etc.)
  - google: Gemini (gemini-2.0-flash, gemini-2.5-pro, etc.)
  - local: Any OpenAI-compatible local server (Ollama, vLLM, LM Studio)
  - tova: Custom fine-tuned Tova model served via Ollama/vLLM

Open-source reasoning model support:
  - Automatic model selection from the registry based on task + hardware
  - Thinking token parsing for reasoning models (GLM-5, DeepSeek-V3.2, etc.)
  - Separate reasoning/vision model routing
"""

import logging
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.callbacks import CallbackManagerForLLMRun

from tova_core.config import get_settings

logger = logging.getLogger(__name__)


def build_llm(
    temperature: float | None = None,
    model_override: str | None = None,
    provider_override: str | None = None,
    api_key_override: str | None = None,
    max_tokens_override: int | None = None,
) -> BaseChatModel:
    """Build a ChatModel from the configured or overridden provider settings.

    Priority: explicit overrides > agent config > server env vars.

    Args:
        temperature: Override the default temperature.
        model_override: Use a specific model (e.g., "claude-sonnet-4-6", "gpt-4o-mini").
        provider_override: Use a specific provider (anthropic, openai, google, local, tova).
        api_key_override: Use a specific API key instead of the server default.
        max_tokens_override: Override max tokens.
    """
    settings = get_settings()
    provider = (provider_override or settings.llm_provider).lower()
    model = model_override or settings.agent_model
    temp = temperature if temperature is not None else settings.agent_temperature
    max_tokens = max_tokens_override or settings.agent_max_tokens

    # If an open-source model ID is configured, resolve it to an Ollama tag
    if settings.oss_model_id and not model_override:
        model, provider = _resolve_oss_model(settings.oss_model_id, provider)

    logger.info(f"Building LLM: provider={provider}, model={model}")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        api_key = api_key_override or settings.anthropic_api_key
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when llm_provider=anthropic")
        return ChatAnthropic(
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temp,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        api_key = api_key_override or settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when llm_provider=openai")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temp,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = api_key_override or settings.google_api_key
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required when llm_provider=google")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            max_output_tokens=max_tokens,
            temperature=temp,
        )

    elif provider in ("local", "tova"):
        from langchain_openai import ChatOpenAI

        base_url = settings.local_llm_base_url

        # For "tova" provider, point at the fine-tuned model
        if provider == "tova":
            if settings.tova_model_path:
                model = settings.tova_model_path
            else:
                model = "tova:latest"
            logger.info(f"Using custom Tova model: {model}")

        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key_override or "not-needed",
            max_tokens=max_tokens,
            temperature=temp,
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            f"Supported: anthropic, openai, google, local, tova"
        )


def build_reasoning_llm(
    temperature: float | None = None,
    max_thinking_tokens: int | None = None,
) -> BaseChatModel:
    """Build a reasoning-capable LLM for complex tasks.

    Uses the configured reasoning model (e.g., GLM-5, DeepSeek-V3.2) or
    falls back to the default model. Reasoning models produce chain-of-thought
    tokens wrapped in <think>...</think> tags.
    """
    settings = get_settings()
    model_id = settings.reasoning_model_id

    if not model_id:
        # Fall back to default model
        return build_llm(temperature=temperature)

    model, provider = _resolve_oss_model(model_id, "local")
    return build_llm(
        temperature=temperature or 0.1,  # lower temp for reasoning
        model_override=model,
        provider_override=provider,
        max_tokens_override=max_thinking_tokens or settings.thinking_budget,
    )


def build_vision_llm(
    temperature: float | None = None,
) -> BaseChatModel:
    """Build a vision-capable LLM for multimodal tasks.

    Uses the configured vision model (e.g., Qwen3-VL, InternVL 3) or
    falls back to the default model.
    """
    settings = get_settings()
    model_id = settings.vision_model_id

    if not model_id:
        return build_llm(temperature=temperature)

    model, provider = _resolve_oss_model(model_id, "local")
    return build_llm(
        temperature=temperature,
        model_override=model,
        provider_override=provider,
    )


def _resolve_oss_model(model_id: str, fallback_provider: str) -> tuple[str, str]:
    """Resolve an open-source model ID to (model_name, provider).

    Looks up the model in the registry and returns the Ollama tag
    for local serving.
    """
    try:
        from tova_core.models.open_source_models import get_model
        spec = get_model(model_id)
        if spec:
            tag = spec.ollama_tag or spec.hf_repo or model_id
            logger.info(f"Resolved OSS model '{model_id}' → {tag}")
            return tag, "local"
    except ImportError:
        logger.debug("open_source_models not available, using model_id as-is")

    return model_id, fallback_provider


# ── Thinking Token Parsing ────────────────────────────────────────────

# Pattern to extract thinking content from reasoning models
_THINK_PATTERN = re.compile(
    r"<think>(.*?)</think>",
    re.DOTALL,
)


def parse_thinking_response(text: str) -> dict[str, str]:
    """Parse a response from a reasoning model that may contain thinking tokens.

    Many open-source reasoning models (DeepSeek-R1, GLM-5, QwQ, etc.) wrap
    their chain-of-thought in <think>...</think> tags.

    Returns:
        {
            "thinking": "the chain-of-thought reasoning (if any)",
            "response": "the final answer with thinking tokens stripped",
        }
    """
    thinking_parts = []
    for match in _THINK_PATTERN.finditer(text):
        thinking_parts.append(match.group(1).strip())

    response = _THINK_PATTERN.sub("", text).strip()

    return {
        "thinking": "\n\n".join(thinking_parts) if thinking_parts else "",
        "response": response,
    }


def auto_select_model(
    task: str = "reasoning",
    require_vision: bool = False,
) -> str | None:
    """Auto-select the best open-source model for a task based on available hardware.

    Returns the model ID, or None if no suitable model is found.
    """
    settings = get_settings()
    try:
        from tova_core.models.open_source_models import select_model
        spec = select_model(
            task=task,
            available_vram_gb=settings.available_vram_gb,
            require_vision=require_vision,
            require_thinking=(task in ("reasoning", "math", "agentic")),
        )
        if spec:
            return spec.id
    except ImportError:
        pass
    return None
