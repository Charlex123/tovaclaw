"""
Tova configuration — loads from .env file or environment variables.

Supports multiple LLM providers: anthropic, openai, google, local (Ollama/vLLM).
Includes open-source reasoning model selection and self-training configuration.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class TovaSettings(BaseSettings):
    # ── LLM Provider ──────────────────────────────────────────
    # Supported: "anthropic", "openai", "google", "local", "tova"
    # "tova" = custom fine-tuned model served locally
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
    # Examples: claude-opus-4-6, gpt-4o, gemini-2.0-flash, glm-5, deepseek-v3.2-speciale
    agent_model: str = "claude-sonnet-4-6"

    # ── Open-Source Model Selection ──────────────────────────
    # Override to use a specific open-source model from the registry.
    # Set llm_provider="local" and this to a model ID from open_source_models.py
    # Values: glm-5, deepseek-v3.2-speciale, kimi-k2.5, gpt-oss-120b, qwen3-235b
    #         qwen3-vl-235b, internvl3-78b, llama-4-scout, gemma-3-27b
    oss_model_id: str = ""  # empty = use agent_model directly

    # Reasoning model config
    reasoning_model_id: str = ""  # separate reasoning model for complex tasks
    enable_thinking_tokens: bool = True  # parse <think> tokens from reasoning models
    thinking_budget: int = 4096  # max tokens for reasoning chain

    # Vision model config
    vision_model_id: str = ""  # separate model for vision/multimodal tasks
    available_vram_gb: float = 24.0  # VRAM for auto-model selection

    # ── Agent Config ──────────────────────────────────────────
    agent_max_iterations: int = 15
    agent_temperature: float = 0.3
    agent_max_tokens: int = 4096
    log_level: str = "INFO"

    # ── Tova Self-Training ────────────────────────────────────
    # The "Tova" model — fine-tuned from usage data
    tova_training_enabled: bool = False  # master switch for self-training
    tova_training_consent_required: bool = True  # require explicit user consent
    tova_training_base_model: str = "glm-5"  # base model ID for fine-tuning
    tova_training_method: str = "qlora"  # lora, qlora, full
    tova_training_output_dir: str = ""  # empty = ~/.tova/models/
    tova_training_min_samples: int = 500  # min samples before first training
    tova_training_auto_trigger: bool = False  # auto-train when enough samples
    tova_training_schedule: str = ""  # cron expression for scheduled training
    tova_model_path: str = ""  # path to trained Tova model (for serving)

    # ── Data Collection Ethics ────────────────────────────────
    # All data collection requires explicit consent. Users can opt out at any time.
    data_collection_consent: bool = False  # global opt-in for training data collection
    data_anonymize_pii: bool = True  # strip PII before storing training data
    data_retention_days: int = 90  # auto-delete training data after N days (0 = keep forever)
    data_export_enabled: bool = True  # allow users to export their training data
    data_deletion_enabled: bool = True  # allow users to request full data deletion
    data_local_only: bool = True  # training data never leaves the local machine

    # ── RAG / Embedding Config ─────────────────────────────────
    embedding_provider: str = "openai"  # openai, google, cohere, local
    embedding_model: str = ""  # Auto-selected per provider if empty
    embedding_api_key: str = ""  # Uses main provider key if empty
    vector_store_provider: str = "chromadb"  # chromadb, pinecone, qdrant
    chunk_size: int = 512
    chunk_overlap: int = 50

    # ── Telephony Config ───────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # ── Auth Config (standalone mode) ─────────────────────────
    # Supported: "session" (default), "none", "apikey", "jwt"
    tova_auth: str = "session"
    tova_session_max_age_days: int = 0  # 0 = never expires
    tova_session_cookie: str = "tova_session"
    tova_user_id: str = "local_user"  # For auth=none
    tova_api_keys: str = ""  # For auth=apikey (comma-separated key:user_id)
    tova_jwt_secret: str = ""  # For auth=jwt
    tova_jwt_algorithm: str = "HS256"
    tova_jwt_user_claim: str = "sub"

    # ── Store Config (standalone mode) ─────────────────────────
    tova_store_db: str = ""  # SQLite path, empty = ~/.tova/tova.db

    # ── Real-time Config ───────────────────────────────────────
    video_analysis_interval: int = 5  # seconds between frame analysis
    gps_poll_interval: int = 30  # seconds between GPS polls
    emergency_check_interval: int = 30  # seconds between escalation checks
    speed_limit_kmh: float = 120.0  # default speed limit for alerts

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> TovaSettings:
    return TovaSettings()
