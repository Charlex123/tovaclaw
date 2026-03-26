"""
Model management tools — install, check, and manage local LLM models.

These tools let Tova (and users) manage the local model infrastructure:
1. Check if Ollama is running
2. List installed models
3. Pull/install new models from the registry
4. Get hardware-aware model recommendations
5. Check model status and health

Works with Ollama (default) and any OpenAI-compatible local server.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
from langchain_core.tools import tool

from tova_core.config import get_settings

logger = logging.getLogger(__name__)


def _get_ollama_base() -> str:
    """Get Ollama base URL (without /v1 suffix)."""
    settings = get_settings()
    url = settings.local_llm_base_url
    # Strip /v1 suffix for Ollama's native API
    if url.endswith("/v1"):
        url = url[:-3]
    return url


def build_model_tools() -> list:
    """Build model management tools."""

    @tool
    async def check_model_status() -> dict:
        """Check if the local LLM server (Ollama) is running and list installed models.

        Returns server status, installed models, and the currently configured model.
        Use this to diagnose issues or see what's available.
        """
        settings = get_settings()
        base_url = _get_ollama_base()

        result = {
            "configured_provider": settings.llm_provider,
            "configured_model": settings.agent_model,
            "ollama_url": base_url,
        }

        # Check if Ollama is running
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("models", [])
                    result["server_running"] = True
                    result["installed_models"] = [
                        {
                            "name": m.get("name", ""),
                            "size_gb": round(m.get("size", 0) / 1e9, 1),
                            "modified": m.get("modified_at", ""),
                            "family": m.get("details", {}).get("family", ""),
                        }
                        for m in models
                    ]
                    result["model_count"] = len(models)

                    # Check if the configured model is installed
                    installed_names = {m.get("name", "") for m in models}
                    # Also check without tag suffix
                    installed_base = {n.split(":")[0] for n in installed_names}
                    configured_base = settings.agent_model.split(":")[0]

                    result["configured_model_installed"] = (
                        settings.agent_model in installed_names
                        or configured_base in installed_base
                    )

                    if not result["configured_model_installed"]:
                        result["action_needed"] = (
                            f"Run: ollama pull {settings.agent_model}"
                        )
                else:
                    result["server_running"] = False
                    result["error"] = f"Ollama responded with status {resp.status_code}"
        except httpx.ConnectError:
            result["server_running"] = False
            result["error"] = "Cannot connect to Ollama"
            result["setup_instructions"] = (
                "1. Install Ollama: https://ollama.com/download\n"
                "2. Start it: ollama serve\n"
                f"3. Pull a model: ollama pull {settings.agent_model}\n"
                "4. Restart Tova"
            )
        except Exception as e:
            result["server_running"] = False
            result["error"] = str(e)

        return result

    @tool
    async def install_model(
        model_name: str = "",
        model_id: str = "",
    ) -> dict:
        """Install (pull) a model via Ollama.

        Either provide a direct Ollama model name or a model ID from the registry.

        Args:
            model_name: Direct Ollama model name (e.g. "qwen3:32b", "qwen2.5-coder:32b-instruct")
            model_id: Model ID from the open-source registry (e.g. "qwen3-32b", "devstral")
        """
        if not model_name and not model_id:
            return {"error": "Provide either model_name or model_id"}

        # Resolve model_id to Ollama tag
        if model_id and not model_name:
            try:
                from tova_core.models.open_source_models import get_model
                spec = get_model(model_id)
                if spec and spec.ollama_tag:
                    model_name = spec.ollama_tag
                else:
                    return {"error": f"Model '{model_id}' not found in registry or has no Ollama tag"}
            except ImportError:
                return {"error": "Model registry not available"}

        base_url = _get_ollama_base()

        # Start the pull via Ollama API
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                # Stream the pull progress
                async with client.stream(
                    "POST",
                    f"{base_url}/api/pull",
                    json={"name": model_name, "stream": True},
                ) as resp:
                    if resp.status_code != 200:
                        return {
                            "error": f"Ollama returned status {resp.status_code}",
                            "model": model_name,
                        }

                    last_status = ""
                    async for line in resp.aiter_lines():
                        if line.strip():
                            try:
                                import json
                                data = json.loads(line)
                                last_status = data.get("status", "")
                            except Exception:
                                pass

                    return {
                        "success": True,
                        "model": model_name,
                        "status": last_status or "completed",
                        "message": f"Model '{model_name}' is now installed and ready to use.",
                    }
        except httpx.ConnectError:
            return {
                "error": "Ollama is not running",
                "fix": "Start Ollama first: ollama serve",
            }
        except httpx.ReadTimeout:
            return {
                "model": model_name,
                "status": "downloading",
                "message": (
                    f"Model '{model_name}' is being downloaded. "
                    f"Large models can take a while. "
                    f"You can also run: ollama pull {model_name}"
                ),
            }
        except Exception as e:
            return {"error": str(e), "model": model_name}

    @tool
    async def recommend_models(
        task: str = "general",
        vram_gb: float = 0,
    ) -> dict:
        """Get model recommendations based on task and available hardware.

        Args:
            task: What you need the model for — general, coding, reasoning, math, agentic, vision
            vram_gb: Available VRAM in GB (0 = use configured value)
        """
        settings = get_settings()
        available_vram = vram_gb or settings.available_vram_gb

        try:
            from tova_core.models.open_source_models import (
                RECOMMENDED, ALL_MODELS, select_model, CODING_MODELS,
            )

            result = {
                "task": task,
                "available_vram_gb": available_vram,
                "recommendations": [],
            }

            # Primary recommendation
            rec_id = RECOMMENDED.get(task)
            if rec_id and rec_id in ALL_MODELS:
                primary = ALL_MODELS[rec_id]
                result["primary_recommendation"] = {
                    "id": primary.id,
                    "name": primary.name,
                    "ollama_tag": primary.ollama_tag,
                    "vram_required_gb": primary.recommended_vram_gb,
                    "fits_hardware": primary.recommended_vram_gb <= available_vram,
                    "install_command": f"ollama pull {primary.ollama_tag}",
                    "benchmarks": primary.benchmark_scores,
                }

            # Hardware-aware selection (might differ from primary if VRAM is limited)
            best = select_model(
                task=task,
                available_vram_gb=available_vram,
                require_tool_calling=(task in ("agentic", "coding")),
            )
            if best:
                result["best_for_your_hardware"] = {
                    "id": best.id,
                    "name": best.name,
                    "ollama_tag": best.ollama_tag,
                    "vram_required_gb": best.recommended_vram_gb,
                    "install_command": f"ollama pull {best.ollama_tag}",
                }

            # For coding tasks, show all coding models
            if task in ("coding", "coding_light", "coding_agentic"):
                coding_list = []
                for model_id, spec in CODING_MODELS.items():
                    coding_list.append({
                        "id": spec.id,
                        "name": spec.name,
                        "ollama_tag": spec.ollama_tag,
                        "vram_required_gb": spec.recommended_vram_gb,
                        "fits_hardware": spec.recommended_vram_gb <= available_vram,
                        "benchmarks": spec.benchmark_scores,
                    })
                result["all_coding_models"] = coding_list

            # All available models as quick reference
            all_recs = {}
            for task_name, mid in RECOMMENDED.items():
                if mid in ALL_MODELS:
                    m = ALL_MODELS[mid]
                    all_recs[task_name] = {
                        "model": m.name,
                        "ollama_tag": m.ollama_tag,
                        "vram_gb": m.recommended_vram_gb,
                    }
            result["all_recommendations"] = all_recs

            return result

        except ImportError:
            return {
                "error": "Model registry not available",
                "fallback": {
                    "general": "ollama pull qwen3:32b",
                    "coding": "ollama pull qwen2.5-coder:32b-instruct",
                    "lightweight": "ollama pull qwen3:8b",
                },
            }

    @tool
    async def list_available_models() -> dict:
        """List all open-source models in the Tova registry.

        Shows every model Tova knows about, with specs, benchmarks,
        VRAM requirements, and install commands.
        """
        try:
            from tova_core.models.open_source_models import ALL_MODELS, RECOMMENDED

            models = []
            for model_id, spec in ALL_MODELS.items():
                # Find which recommendation categories this model appears in
                rec_for = [task for task, mid in RECOMMENDED.items() if mid == model_id]

                models.append({
                    "id": spec.id,
                    "name": spec.name,
                    "provider": spec.provider,
                    "parameters": spec.parameters,
                    "context_window": spec.context_window,
                    "ollama_tag": spec.ollama_tag,
                    "vram_required_gb": spec.recommended_vram_gb,
                    "strengths": [s.value for s in spec.strengths],
                    "benchmarks": spec.benchmark_scores,
                    "recommended_for": rec_for,
                    "install_command": f"ollama pull {spec.ollama_tag}" if spec.ollama_tag else "N/A",
                })

            return {
                "total_models": len(models),
                "models": models,
            }
        except ImportError:
            return {"error": "Model registry not available"}

    return [
        check_model_status,
        install_model,
        recommend_models,
        list_available_models,
    ]
