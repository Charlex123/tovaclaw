"""
Open-Source Model Registry — curated catalog of best-in-class open models.

Tova selects from this registry based on task requirements:
  - Reasoning: GLM-5, DeepSeek-V3.2, Kimi-K2.5, gpt-oss-120B, Qwen3-235B
  - Vision: Qwen3-VL, InternVL 3, Llama 4 Scout, Gemma 3
  - Tova (custom): Fine-tuned from usage data on a base model

Each model entry includes serving metadata (Ollama tag, vLLM path, required VRAM)
so the runtime can auto-select a model that fits the available hardware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelCategory(str, Enum):
    REASONING = "reasoning"
    VISION = "vision"
    GENERAL = "general"
    CUSTOM = "custom"  # fine-tuned Tova models


class ModelStrength(str, Enum):
    TOP_OVERALL = "top_overall"
    MATH_CODING = "math_coding"
    CODING = "coding"
    AGENTIC = "agentic"
    INSTRUCTION_FOLLOWING = "instruction_following"
    GENERAL_KNOWLEDGE = "general_knowledge"
    VISION_OCR = "vision_ocr"
    SPATIAL_3D = "spatial_3d"
    MULTIMODAL_SPEED = "multimodal_speed"
    ON_DEVICE = "on_device"
    CODING_ON_DEVICE = "coding_on_device"


@dataclass
class ModelSpec:
    """Specification for an open-source model."""

    id: str  # unique identifier
    name: str  # display name
    category: ModelCategory
    strength: ModelStrength
    description: str

    # Serving identifiers
    ollama_tag: str = ""  # e.g. "glm5:latest"
    hf_repo: str = ""  # e.g. "THUDM/glm-5-9b-chat"
    vllm_model: str = ""  # model path for vLLM serving

    # Hardware requirements
    min_vram_gb: float = 0  # minimum VRAM in GB
    recommended_vram_gb: float = 0
    parameters_b: float = 0  # parameter count in billions
    quantization: str = ""  # e.g. "Q4_K_M", "AWQ", "GPTQ"

    # Capabilities
    supports_tool_calling: bool = True
    supports_thinking: bool = False  # reasoning/chain-of-thought
    supports_vision: bool = False
    max_context_length: int = 32768
    languages: list[str] = field(default_factory=lambda: ["en"])

    # Fine-tuning suitability
    fine_tune_base: bool = False  # suitable as base for Tova fine-tuning
    lora_target_modules: list[str] = field(default_factory=list)

    # Performance metadata
    benchmark_scores: dict[str, float] = field(default_factory=dict)

    def fits_hardware(self, available_vram_gb: float) -> bool:
        """Check if this model can run on available hardware."""
        return self.min_vram_gb <= available_vram_gb


# ── Reasoning Models ─────────────────────────────────────────────────────

GLM_5 = ModelSpec(
    id="glm-5",
    name="GLM-5 (Reasoning)",
    category=ModelCategory.REASONING,
    strength=ModelStrength.TOP_OVERALL,
    description=(
        "Currently ranked #1 on open-source leaderboards. "
        "Excels at systems engineering and complex logic."
    ),
    ollama_tag="glm5:latest",
    hf_repo="THUDM/glm-5-chat",
    vllm_model="THUDM/glm-5-chat",
    min_vram_gb=16,
    recommended_vram_gb=24,
    parameters_b=9,
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    benchmark_scores={"mmlu": 0.82, "humaneval": 0.78, "math": 0.85},
)

DEEPSEEK_V3_2 = ModelSpec(
    id="deepseek-v3.2-speciale",
    name="DeepSeek-V3.2 Speciale",
    category=ModelCategory.REASONING,
    strength=ModelStrength.MATH_CODING,
    description=(
        "Reaches GPT-5 level reasoning on math benchmarks like AIME. "
        "Highly efficient for agentic tasks."
    ),
    ollama_tag="deepseek-v3.2:latest",
    hf_repo="deepseek-ai/DeepSeek-V3.2-Speciale",
    vllm_model="deepseek-ai/DeepSeek-V3.2-Speciale",
    min_vram_gb=16,
    recommended_vram_gb=48,
    parameters_b=671,  # MoE, active ~37B
    quantization="AWQ",
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    benchmark_scores={"aime": 0.92, "humaneval": 0.89, "math": 0.94, "mmlu": 0.88},
)

KIMI_K2_5 = ModelSpec(
    id="kimi-k2.5",
    name="Kimi-K2.5",
    category=ModelCategory.REASONING,
    strength=ModelStrength.AGENTIC,
    description=(
        "1-trillion parameter MoE model designed to orchestrate up to 100 "
        "sub-agents for massive research tasks."
    ),
    ollama_tag="kimi-k2.5:latest",
    hf_repo="moonshotai/Kimi-K2.5",
    vllm_model="moonshotai/Kimi-K2.5",
    min_vram_gb=48,
    recommended_vram_gb=80,
    parameters_b=1000,  # MoE
    quantization="AWQ",
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=262144,
    benchmark_scores={"mmlu": 0.90, "agentic_bench": 0.95},
)

GPT_OSS_120B = ModelSpec(
    id="gpt-oss-120b",
    name="gpt-oss-120B",
    category=ModelCategory.REASONING,
    strength=ModelStrength.INSTRUCTION_FOLLOWING,
    description=(
        "OpenAI's flagship open-weight release. Provides high-level reasoning "
        "that rivals proprietary o4-mini."
    ),
    ollama_tag="gpt-oss:120b",
    hf_repo="openai/gpt-oss-120b",
    vllm_model="openai/gpt-oss-120b",
    min_vram_gb=48,
    recommended_vram_gb=80,
    parameters_b=120,
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=128000,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    benchmark_scores={"mmlu": 0.89, "humaneval": 0.86, "instruction_following": 0.93},
)

QWEN3_235B = ModelSpec(
    id="qwen3-235b",
    name="Qwen3-235B",
    category=ModelCategory.GENERAL,
    strength=ModelStrength.GENERAL_KNOWLEDGE,
    description=(
        "Top-performing non-reasoning model. Holds the highest MMLU (knowledge) "
        "scores. Best for broad general knowledge without deep thinking overhead."
    ),
    ollama_tag="qwen3:235b",
    hf_repo="Qwen/Qwen3-235B",
    vllm_model="Qwen/Qwen3-235B",
    min_vram_gb=48,
    recommended_vram_gb=80,
    parameters_b=235,  # MoE
    quantization="AWQ",
    supports_thinking=False,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    benchmark_scores={"mmlu": 0.92, "humaneval": 0.82},
)


# ── Coding Models ────────────────────────────────────────────────────────

QWEN2_5_CODER_32B = ModelSpec(
    id="qwen2.5-coder-32b",
    name="Qwen2.5-Coder 32B Instruct",
    category=ModelCategory.REASONING,
    strength=ModelStrength.CODING,
    description=(
        "Best open-source coding model. Outperforms GPT-4o on coding benchmarks. "
        "Supports 92 programming languages. Excellent at code generation, "
        "debugging, refactoring, and code review."
    ),
    ollama_tag="qwen2.5-coder:32b-instruct",
    hf_repo="Qwen/Qwen2.5-Coder-32B-Instruct",
    vllm_model="Qwen/Qwen2.5-Coder-32B-Instruct",
    min_vram_gb=20,
    recommended_vram_gb=24,
    parameters_b=32,
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    benchmark_scores={"humaneval": 0.92, "mbpp": 0.90, "coding": 0.91, "mmlu": 0.83},
)

QWEN2_5_CODER_7B = ModelSpec(
    id="qwen2.5-coder-7b",
    name="Qwen2.5-Coder 7B Instruct",
    category=ModelCategory.REASONING,
    strength=ModelStrength.CODING_ON_DEVICE,
    description=(
        "Compact coding model that runs on consumer hardware. "
        "Strong coding capability for its size — outperforms much larger models."
    ),
    ollama_tag="qwen2.5-coder:7b-instruct",
    hf_repo="Qwen/Qwen2.5-Coder-7B-Instruct",
    vllm_model="Qwen/Qwen2.5-Coder-7B-Instruct",
    min_vram_gb=6,
    recommended_vram_gb=8,
    parameters_b=7,
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    benchmark_scores={"humaneval": 0.83, "mbpp": 0.80, "coding": 0.82},
)

DEEPSEEK_CODER_V2 = ModelSpec(
    id="deepseek-coder-v2",
    name="DeepSeek-Coder-V2 236B",
    category=ModelCategory.REASONING,
    strength=ModelStrength.CODING,
    description=(
        "MoE coding specialist from DeepSeek. 236B total parameters with "
        "21B active. Excellent at code generation, math, and reasoning."
    ),
    ollama_tag="deepseek-coder-v2:236b",
    hf_repo="deepseek-ai/DeepSeek-Coder-V2-Instruct",
    vllm_model="deepseek-ai/DeepSeek-Coder-V2-Instruct",
    min_vram_gb=16,
    recommended_vram_gb=48,
    parameters_b=236,  # MoE, active ~21B
    quantization="AWQ",
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    benchmark_scores={"humaneval": 0.90, "mbpp": 0.88, "coding": 0.89, "math": 0.87},
)

CODESTRAL_25_01 = ModelSpec(
    id="codestral-25.01",
    name="Codestral 25.01",
    category=ModelCategory.REASONING,
    strength=ModelStrength.CODING,
    description=(
        "Mistral's flagship code model. 32B parameters with 256K context. "
        "Optimized for code completion, generation, and instruction following."
    ),
    ollama_tag="codestral:latest",
    hf_repo="mistralai/Codestral-25.01",
    vllm_model="mistralai/Codestral-25.01",
    min_vram_gb=20,
    recommended_vram_gb=24,
    parameters_b=32,
    supports_thinking=False,
    supports_tool_calling=True,
    max_context_length=262144,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    benchmark_scores={"humaneval": 0.88, "mbpp": 0.87, "coding": 0.88},
)

STARCODER2_15B = ModelSpec(
    id="starcoder2-15b",
    name="StarCoder2 15B",
    category=ModelCategory.REASONING,
    strength=ModelStrength.CODING_ON_DEVICE,
    description=(
        "Efficient code model from BigCode. Trained on The Stack v2 — "
        "619 programming languages. Best coding model under 16B params."
    ),
    ollama_tag="starcoder2:15b",
    hf_repo="bigcode/starcoder2-15b-instruct",
    vllm_model="bigcode/starcoder2-15b-instruct",
    min_vram_gb=10,
    recommended_vram_gb=16,
    parameters_b=15,
    supports_thinking=False,
    supports_tool_calling=True,
    max_context_length=16384,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    benchmark_scores={"humaneval": 0.76, "mbpp": 0.74, "coding": 0.75},
)

DEVSTRAL = ModelSpec(
    id="devstral",
    name="Devstral Small",
    category=ModelCategory.REASONING,
    strength=ModelStrength.CODING,
    description=(
        "Mistral's agentic coding model. Specifically designed for AI coding agents — "
        "excels at tool use, multi-file editing, and codebase navigation. "
        "SWE-bench verified score of 46.8%."
    ),
    ollama_tag="devstral:latest",
    hf_repo="mistralai/Devstral-Small-2507",
    vllm_model="mistralai/Devstral-Small-2507",
    min_vram_gb=16,
    recommended_vram_gb=24,
    parameters_b=24,
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    benchmark_scores={"swe_bench": 0.468, "humaneval": 0.85, "coding": 0.87, "agentic": 0.90},
)

QWEN3_32B = ModelSpec(
    id="qwen3-32b",
    name="Qwen3-32B",
    category=ModelCategory.REASONING,
    strength=ModelStrength.TOP_OVERALL,
    description=(
        "Qwen3's best balanced model. Strong reasoning with thinking mode, "
        "excellent coding, 128K context, tool calling support. "
        "Runs comfortably on 24GB VRAM. Great default for Tova."
    ),
    ollama_tag="qwen3:32b",
    hf_repo="Qwen/Qwen3-32B",
    vllm_model="Qwen/Qwen3-32B",
    min_vram_gb=20,
    recommended_vram_gb=24,
    parameters_b=32,
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    benchmark_scores={"mmlu": 0.86, "humaneval": 0.85, "math": 0.83, "coding": 0.85, "agentic": 0.88},
)

QWEN3_8B = ModelSpec(
    id="qwen3-8b",
    name="Qwen3-8B",
    category=ModelCategory.GENERAL,
    strength=ModelStrength.ON_DEVICE,
    description=(
        "Lightweight but capable. Runs on 8GB VRAM. Thinking mode, tool calling, "
        "128K context. Best small model for resource-constrained setups."
    ),
    ollama_tag="qwen3:8b",
    hf_repo="Qwen/Qwen3-8B",
    vllm_model="Qwen/Qwen3-8B",
    min_vram_gb=6,
    recommended_vram_gb=8,
    parameters_b=8,
    supports_thinking=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    benchmark_scores={"mmlu": 0.74, "humaneval": 0.72, "coding": 0.73},
)


# ── Vision & Multimodal Models ───────────────────────────────────────────

QWEN3_VL = ModelSpec(
    id="qwen3-vl-235b",
    name="Qwen3-VL (235B)",
    category=ModelCategory.VISION,
    strength=ModelStrength.VISION_OCR,
    description=(
        "Gold standard for open-source vision. Supports OCR across 32+ languages "
        "and is widely used for GUI automation."
    ),
    ollama_tag="qwen3-vl:235b",
    hf_repo="Qwen/Qwen3-VL-235B",
    vllm_model="Qwen/Qwen3-VL-235B",
    min_vram_gb=48,
    recommended_vram_gb=80,
    parameters_b=235,
    supports_vision=True,
    supports_tool_calling=True,
    max_context_length=131072,
    languages=["en", "zh", "ja", "ko", "ar", "he", "fr", "de", "es", "pt", "ru"],
    benchmark_scores={"ocr": 0.95, "gui_automation": 0.91},
)

INTERNVL_3 = ModelSpec(
    id="internvl3-78b",
    name="InternVL 3-78B",
    category=ModelCategory.VISION,
    strength=ModelStrength.SPATIAL_3D,
    description=(
        "State-of-the-art multimodal perception. Particularly strong at "
        "3D spatial reasoning and industrial image analysis."
    ),
    ollama_tag="internvl3:78b",
    hf_repo="OpenGVLab/InternVL3-78B",
    vllm_model="OpenGVLab/InternVL3-78B",
    min_vram_gb=40,
    recommended_vram_gb=80,
    parameters_b=78,
    supports_vision=True,
    supports_tool_calling=True,
    max_context_length=65536,
    benchmark_scores={"spatial_3d": 0.93, "industrial_vision": 0.90},
)

LLAMA_4_SCOUT = ModelSpec(
    id="llama-4-scout",
    name="Llama 4 Scout",
    category=ModelCategory.VISION,
    strength=ModelStrength.MULTIMODAL_SPEED,
    description=(
        "Distilled, high-speed multimodal model from Meta. Optimized for "
        "real-world speed and handles multi-image prompts exceptionally well."
    ),
    ollama_tag="llama4-scout:latest",
    hf_repo="meta-llama/Llama-4-Scout",
    vllm_model="meta-llama/Llama-4-Scout",
    min_vram_gb=16,
    recommended_vram_gb=24,
    parameters_b=17,  # MoE, 109B total
    supports_vision=True,
    supports_tool_calling=True,
    max_context_length=1048576,
    benchmark_scores={"speed_multimodal": 0.92, "multi_image": 0.88},
)

GEMMA_3 = ModelSpec(
    id="gemma-3-27b",
    name="Gemma 3 (27B)",
    category=ModelCategory.VISION,
    strength=ModelStrength.ON_DEVICE,
    description=(
        "Best for local/on-device vision. Small enough to run on a single "
        "consumer GPU while maintaining strong multimodal capabilities."
    ),
    ollama_tag="gemma3:27b",
    hf_repo="google/gemma-3-27b-it",
    vllm_model="google/gemma-3-27b-it",
    min_vram_gb=8,
    recommended_vram_gb=16,
    parameters_b=27,
    supports_vision=True,
    supports_tool_calling=True,
    max_context_length=131072,
    fine_tune_base=True,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    benchmark_scores={"on_device_vision": 0.85, "mmlu": 0.75},
)


# ── Model Registry ───────────────────────────────────────────────────────

ALL_MODELS: dict[str, ModelSpec] = {
    m.id: m for m in [
        # Reasoning
        GLM_5, DEEPSEEK_V3_2, KIMI_K2_5, GPT_OSS_120B, QWEN3_235B,
        # General (balanced)
        QWEN3_32B, QWEN3_8B,
        # Coding
        QWEN2_5_CODER_32B, QWEN2_5_CODER_7B, DEEPSEEK_CODER_V2,
        CODESTRAL_25_01, STARCODER2_15B, DEVSTRAL,
        # Vision
        QWEN3_VL, INTERNVL_3, LLAMA_4_SCOUT, GEMMA_3,
    ]
}

REASONING_MODELS = {k: v for k, v in ALL_MODELS.items() if v.category == ModelCategory.REASONING}
CODING_MODELS = {k: v for k, v in ALL_MODELS.items() if v.strength in (ModelStrength.CODING, ModelStrength.CODING_ON_DEVICE, ModelStrength.MATH_CODING)}
VISION_MODELS = {k: v for k, v in ALL_MODELS.items() if v.category == ModelCategory.VISION}
GENERAL_MODELS = {k: v for k, v in ALL_MODELS.items() if v.category == ModelCategory.GENERAL}

# Models suitable as base for fine-tuning the "Tova" custom model
FINE_TUNE_BASES = {k: v for k, v in ALL_MODELS.items() if v.fine_tune_base}

# Recommended defaults by use case
RECOMMENDED = {
    "default": "qwen3-32b",  # best balanced model — Tova's default
    "reasoning": "glm-5",
    "math": "deepseek-v3.2-speciale",
    "coding": "qwen2.5-coder-32b",  # best open-source coding model
    "coding_light": "qwen2.5-coder-7b",  # best coding model for low VRAM
    "coding_agentic": "devstral",  # best for AI coding agents (SWE-bench leader)
    "agentic": "kimi-k2.5",
    "instruction": "gpt-oss-120b",
    "general": "qwen3-32b",
    "general_light": "qwen3-8b",  # best lightweight all-rounder
    "vision": "qwen3-vl-235b",
    "spatial": "internvl3-78b",
    "speed": "llama-4-scout",
    "on_device": "qwen3-8b",
    "fine_tune_base": "qwen3-32b",
}


def select_model(
    task: str = "reasoning",
    available_vram_gb: float = 24,
    require_vision: bool = False,
    require_thinking: bool = False,
    require_tool_calling: bool = True,
) -> ModelSpec | None:
    """Auto-select the best model for a given task and hardware constraint.

    Args:
        task: One of the RECOMMENDED keys, or "auto" to pick best overall.
        available_vram_gb: VRAM available on the serving machine.
        require_vision: Only consider models with vision support.
        require_thinking: Only consider models with reasoning/thinking support.
        require_tool_calling: Only consider models with tool calling support.

    Returns:
        Best matching ModelSpec, or None if nothing fits.
    """
    candidates = list(ALL_MODELS.values())

    # Apply hard filters
    candidates = [m for m in candidates if m.fits_hardware(available_vram_gb)]
    if require_vision:
        candidates = [m for m in candidates if m.supports_vision]
    if require_thinking:
        candidates = [m for m in candidates if m.supports_thinking]
    if require_tool_calling:
        candidates = [m for m in candidates if m.supports_tool_calling]

    if not candidates:
        return None

    # Try recommended model for the task
    if task in RECOMMENDED:
        rec_id = RECOMMENDED[task]
        rec = ALL_MODELS.get(rec_id)
        if rec and rec in candidates:
            return rec

    # Fallback: sort by benchmark score sum (higher = better), prefer smaller models
    def score(m: ModelSpec) -> float:
        bench = sum(m.benchmark_scores.values()) / max(len(m.benchmark_scores), 1)
        # Slight preference for models that fit comfortably
        fit_bonus = 0.05 if m.recommended_vram_gb <= available_vram_gb else 0
        return bench + fit_bonus

    candidates.sort(key=score, reverse=True)
    return candidates[0]


def select_fine_tune_base(available_vram_gb: float = 24) -> ModelSpec | None:
    """Select the best base model for fine-tuning the custom Tova model."""
    candidates = [m for m in FINE_TUNE_BASES.values() if m.fits_hardware(available_vram_gb)]
    if not candidates:
        return None

    # Prefer models with highest benchmark scores that fit
    candidates.sort(
        key=lambda m: sum(m.benchmark_scores.values()) / max(len(m.benchmark_scores), 1),
        reverse=True,
    )
    return candidates[0]


def get_model(model_id: str) -> ModelSpec | None:
    """Look up a model by ID."""
    return ALL_MODELS.get(model_id)


def list_models(
    category: ModelCategory | None = None,
    max_vram_gb: float | None = None,
) -> list[ModelSpec]:
    """List available models with optional filters."""
    models = list(ALL_MODELS.values())
    if category:
        models = [m for m in models if m.category == category]
    if max_vram_gb is not None:
        models = [m for m in models if m.fits_hardware(max_vram_gb)]
    return models
