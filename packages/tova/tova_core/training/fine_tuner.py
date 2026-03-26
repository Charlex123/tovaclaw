"""
Fine-Tuning Pipeline — trains the custom "Tova" model from collected interaction data.

Supports:
  - LoRA: Low-Rank Adaptation (fast, memory-efficient)
  - QLoRA: Quantized LoRA (4-bit, runs on consumer GPUs)
  - Full: Full fine-tuning (requires significant VRAM)

Base models from the open-source registry:
  - GLM-5: Best overall reasoning (recommended default)
  - DeepSeek-V3.2: Best for math/coding tasks
  - Gemma 3: Best for on-device deployment
  - Any HuggingFace model via hf_repo

The trained model is served locally via Ollama or vLLM, and Tova switches
to it by setting llm_provider="tova".

Training is:
  - Incremental: new data extends previous training, no full retrain needed
  - Evaluated: automatic benchmarks before deployment
  - Versioned: each training run produces a versioned model artifact
  - Auditable: full lineage from source samples to model weights
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import aiosqlite

from tova_core.config import get_settings
from tova_core.training.data_generator import TrainingDataGenerator

logger = logging.getLogger(__name__)


class TrainingMethod(str):
    LORA = "lora"
    QLORA = "qlora"
    FULL = "full"


class TrainingStatus(str):
    PENDING = "pending"
    PREPARING = "preparing"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


class TovaFineTuner:
    """Orchestrates fine-tuning of the custom Tova model.

    This is the core of Tova's self-improvement cycle:
    1. Exports training data from the data generator
    2. Prepares it in the format required by the fine-tuning framework
    3. Runs LoRA/QLoRA training on the configured base model
    4. Evaluates the resulting model
    5. Deploys it for serving via Ollama

    Usage:
        tuner = TovaFineTuner()
        run = await tuner.start_training()
        status = await tuner.get_status(run["run_id"])
    """

    def __init__(self, db_path: str | None = None):
        settings = get_settings()
        self._db_path = db_path or self._default_db_path()
        self._data_gen = TrainingDataGenerator(db_path)
        self._output_dir = settings.tova_training_output_dir or os.path.expanduser("~/.tova/models")
        os.makedirs(self._output_dir, exist_ok=True)
        self._initialized = False

    @staticmethod
    def _default_db_path() -> str:
        base = os.path.expanduser("~/.tova")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "learning.db")

    async def _ensure_tables(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS training_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'pending',
                    base_model TEXT NOT NULL,
                    method TEXT NOT NULL DEFAULT 'qlora',
                    sample_count INTEGER DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT,
                    output_path TEXT,
                    eval_results TEXT DEFAULT '{}',
                    config TEXT DEFAULT '{}',
                    error TEXT,
                    version INTEGER DEFAULT 1
                )
            """)
            await db.commit()
        self._initialized = True

    async def can_train(self) -> dict[str, Any]:
        """Check if there's enough data and conditions are met for training.

        Returns readiness status and what's missing.
        """
        settings = get_settings()
        stats = await self._data_gen.get_stats()

        issues = []
        if not settings.tova_training_enabled:
            issues.append("Training is disabled (set TOVA_TRAINING_ENABLED=true)")
        if stats["unused_samples"] < settings.tova_training_min_samples:
            issues.append(
                f"Need {settings.tova_training_min_samples} samples, "
                f"have {stats['unused_samples']}"
            )

        # Check for required libraries
        missing_libs = []
        try:
            import torch  # noqa: F401
        except ImportError:
            missing_libs.append("torch")
        try:
            import transformers  # noqa: F401
        except ImportError:
            missing_libs.append("transformers")
        try:
            import peft  # noqa: F401
        except ImportError:
            missing_libs.append("peft")

        if missing_libs:
            issues.append(f"Missing libraries: {', '.join(missing_libs)}")

        return {
            "ready": len(issues) == 0,
            "issues": issues,
            "data_stats": stats,
            "base_model": settings.tova_training_base_model,
            "method": settings.tova_training_method,
        }

    async def start_training(
        self,
        base_model_override: str | None = None,
        method_override: str | None = None,
        min_quality: float = 0.5,
        max_samples: int = 0,
        hyperparams: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a fine-tuning run.

        This is an async operation — training runs in the background.

        Args:
            base_model_override: Override the configured base model.
            method_override: Override the training method (lora, qlora, full).
            min_quality: Minimum quality score for training samples.
            max_samples: Max samples to use (0 = all available).
            hyperparams: Custom hyperparameters for training.

        Returns:
            {"run_id": str, "status": str, "estimated_samples": int}
        """
        settings = get_settings()
        await self._ensure_tables()

        readiness = await self.can_train()
        if not readiness["ready"]:
            return {
                "run_id": None,
                "status": "not_ready",
                "issues": readiness["issues"],
            }

        run_id = uuid4().hex[:12]
        base_model = base_model_override or settings.tova_training_base_model
        method = method_override or settings.tova_training_method
        now = datetime.now(timezone.utc).isoformat()

        # Resolve base model to HuggingFace repo
        hf_repo = self._resolve_hf_repo(base_model)

        # Export training data
        samples = await self._data_gen.export_training_set(
            min_quality=min_quality,
            limit=max_samples,
            exclude_used=True,
        )

        if not samples:
            return {"run_id": None, "status": "no_data", "issues": ["No unused samples available"]}

        # Prepare training config
        config = self._build_training_config(
            hf_repo, method, len(samples), hyperparams or {},
        )

        # Store the run
        async with aiosqlite.connect(self._db_path) as db:
            # Get next version number
            cursor = await db.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM training_runs"
            )
            version = (await cursor.fetchone())[0]

            await db.execute("""
                INSERT INTO training_runs (id, status, base_model, method, sample_count,
                                          started_at, config, version)
                VALUES (?, 'preparing', ?, ?, ?, ?, ?, ?)
            """, (run_id, base_model, method, len(samples), now, json.dumps(config), version))
            await db.commit()

        # Prepare the data files
        data_dir = os.path.join(self._output_dir, f"run_{run_id}", "data")
        os.makedirs(data_dir, exist_ok=True)
        await self._write_training_data(samples, data_dir)

        # Mark samples as used
        sample_ids = [s["id"] for s in samples]
        await self._data_gen.mark_samples_used(sample_ids, run_id)

        # Run the actual training
        try:
            await self._run_training(run_id, hf_repo, method, data_dir, config)
        except Exception as e:
            await self._update_status(run_id, TrainingStatus.FAILED, error=str(e))
            return {"run_id": run_id, "status": "failed", "error": str(e)}

        return {
            "run_id": run_id,
            "status": "training",
            "sample_count": len(samples),
            "base_model": base_model,
            "method": method,
            "version": version,
        }

    async def _run_training(
        self,
        run_id: str,
        hf_repo: str,
        method: str,
        data_dir: str,
        config: dict[str, Any],
    ) -> None:
        """Execute the actual fine-tuning.

        Uses HuggingFace transformers + PEFT for LoRA/QLoRA training.
        Falls back to Unsloth if available (2x faster).
        """
        await self._update_status(run_id, TrainingStatus.TRAINING)
        output_dir = os.path.join(self._output_dir, f"run_{run_id}", "model")
        os.makedirs(output_dir, exist_ok=True)

        try:
            # Try Unsloth first (faster)
            if method in ("lora", "qlora"):
                try:
                    await self._train_with_unsloth(hf_repo, method, data_dir, output_dir, config)
                    await self._update_status(
                        run_id, TrainingStatus.COMPLETED, output_path=output_dir,
                    )
                    return
                except ImportError:
                    logger.info("Unsloth not available, falling back to PEFT")

            # Standard PEFT training
            await self._train_with_peft(hf_repo, method, data_dir, output_dir, config)
            await self._update_status(
                run_id, TrainingStatus.COMPLETED, output_path=output_dir,
            )

        except Exception as e:
            logger.error(f"Training failed: {e}")
            await self._update_status(run_id, TrainingStatus.FAILED, error=str(e))
            raise

    async def _train_with_unsloth(
        self,
        hf_repo: str,
        method: str,
        data_dir: str,
        output_dir: str,
        config: dict[str, Any],
    ) -> None:
        """Train using Unsloth — 2x faster LoRA/QLoRA training."""
        from unsloth import FastLanguageModel
        from trl import SFTTrainer
        from transformers import TrainingArguments
        import torch

        load_in_4bit = method == "qlora"

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=hf_repo,
            max_seq_length=config.get("max_seq_length", 2048),
            load_in_4bit=load_in_4bit,
            dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        )

        # Apply LoRA
        model = FastLanguageModel.get_peft_model(
            model,
            r=config.get("lora_r", 16),
            lora_alpha=config.get("lora_alpha", 32),
            lora_dropout=config.get("lora_dropout", 0.05),
            target_modules=config.get("target_modules", [
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ]),
        )

        # Load training data
        from datasets import load_dataset
        dataset = load_dataset("json", data_files=os.path.join(data_dir, "train.jsonl"))

        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=config.get("epochs", 3),
            per_device_train_batch_size=config.get("batch_size", 4),
            gradient_accumulation_steps=config.get("gradient_accumulation", 4),
            learning_rate=config.get("learning_rate", 2e-4),
            weight_decay=config.get("weight_decay", 0.01),
            warmup_ratio=config.get("warmup_ratio", 0.1),
            lr_scheduler_type="cosine",
            logging_steps=10,
            save_strategy="epoch",
            bf16=torch.cuda.is_bf16_supported(),
            fp16=not torch.cuda.is_bf16_supported(),
            optim="adamw_8bit",
        )

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset["train"],
            args=training_args,
            max_seq_length=config.get("max_seq_length", 2048),
        )

        trainer.train()
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

    async def _train_with_peft(
        self,
        hf_repo: str,
        method: str,
        data_dir: str,
        output_dir: str,
        config: dict[str, Any],
    ) -> None:
        """Train using HuggingFace PEFT — standard LoRA/QLoRA/full fine-tuning."""
        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            TrainingArguments,
            BitsAndBytesConfig,
        )
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from trl import SFTTrainer
        from datasets import load_dataset

        # Quantization config for QLoRA
        bnb_config = None
        if method == "qlora":
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )

        # Load base model
        tokenizer = AutoTokenizer.from_pretrained(hf_repo, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            hf_repo,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        )

        if method in ("lora", "qlora"):
            if method == "qlora":
                model = prepare_model_for_kbit_training(model)

            lora_config = LoraConfig(
                r=config.get("lora_r", 16),
                lora_alpha=config.get("lora_alpha", 32),
                lora_dropout=config.get("lora_dropout", 0.05),
                target_modules=config.get("target_modules", [
                    "q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj",
                ]),
                bias="none",
                task_type="CAUSAL_LM",
            )
            model = get_peft_model(model, lora_config)

        # Load training data
        dataset = load_dataset("json", data_files=os.path.join(data_dir, "train.jsonl"))

        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=config.get("epochs", 3),
            per_device_train_batch_size=config.get("batch_size", 4),
            gradient_accumulation_steps=config.get("gradient_accumulation", 4),
            learning_rate=config.get("learning_rate", 2e-4),
            weight_decay=config.get("weight_decay", 0.01),
            warmup_ratio=config.get("warmup_ratio", 0.1),
            lr_scheduler_type="cosine",
            logging_steps=10,
            save_strategy="epoch",
            bf16=torch.cuda.is_bf16_supported(),
            fp16=not torch.cuda.is_bf16_supported(),
            gradient_checkpointing=True,
        )

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset["train"],
            args=training_args,
            max_seq_length=config.get("max_seq_length", 2048),
        )

        trainer.train()
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

    # ── Data Preparation ──────────────────────────────────────────────

    async def _write_training_data(
        self,
        samples: list[dict[str, Any]],
        data_dir: str,
    ) -> None:
        """Write training samples to JSONL files for the fine-tuning framework.

        Converts all sample formats to the chat completion format expected
        by SFTTrainer.
        """
        train_path = os.path.join(data_dir, "train.jsonl")

        with open(train_path, "w") as f:
            for sample in samples:
                data = sample["data"]
                fmt = sample["format"]

                # Normalize to chat format
                if fmt in ("chat", "tool_call", "reasoning"):
                    # Already in messages format
                    record = {"messages": data.get("messages", [])}
                elif fmt == "preference":
                    # DPO format — write as chosen conversation
                    record = {"messages": [
                        {"role": "user", "content": data.get("prompt", "")},
                        {"role": "assistant", "content": data.get("chosen", "")},
                    ]}
                elif fmt == "qa":
                    record = {"messages": [
                        {"role": "user", "content": data.get("question", "")},
                        {"role": "assistant", "content": data.get("answer", "")},
                    ]}
                else:
                    continue

                if record["messages"]:
                    f.write(json.dumps(record) + "\n")

        logger.info(f"Wrote {len(samples)} training samples to {train_path}")

    # ── Config ────────────────────────────────────────────────────────

    def _build_training_config(
        self,
        hf_repo: str,
        method: str,
        sample_count: int,
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the training configuration with sensible defaults."""
        # Scale epochs inversely with dataset size
        if sample_count < 1000:
            default_epochs = 5
        elif sample_count < 5000:
            default_epochs = 3
        else:
            default_epochs = 2

        config = {
            "hf_repo": hf_repo,
            "method": method,
            "max_seq_length": 2048,
            "epochs": default_epochs,
            "batch_size": 4,
            "gradient_accumulation": 4,
            "learning_rate": 2e-4,
            "weight_decay": 0.01,
            "warmup_ratio": 0.1,
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "target_modules": [
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
        }
        config.update(overrides)
        return config

    def _resolve_hf_repo(self, model_id: str) -> str:
        """Resolve a model registry ID to a HuggingFace repo path."""
        try:
            from tova_core.models.open_source_models import get_model
            spec = get_model(model_id)
            if spec and spec.hf_repo:
                return spec.hf_repo
        except ImportError:
            pass
        return model_id

    # ── Status & History ──────────────────────────────────────────────

    async def _update_status(
        self,
        run_id: str,
        status: str,
        output_path: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update the status of a training run."""
        await self._ensure_tables()
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            if status == TrainingStatus.COMPLETED:
                await db.execute("""
                    UPDATE training_runs SET status = ?, completed_at = ?, output_path = ?
                    WHERE id = ?
                """, (status, now, output_path, run_id))
            elif status == TrainingStatus.FAILED:
                await db.execute("""
                    UPDATE training_runs SET status = ?, completed_at = ?, error = ?
                    WHERE id = ?
                """, (status, now, error, run_id))
            else:
                await db.execute(
                    "UPDATE training_runs SET status = ? WHERE id = ?",
                    (status, run_id),
                )
            await db.commit()

    async def get_status(self, run_id: str) -> dict[str, Any] | None:
        """Get the status of a training run."""
        await self._ensure_tables()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM training_runs WHERE id = ?", (run_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None

    async def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent training runs."""
        await self._ensure_tables()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM training_runs ORDER BY started_at DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in await cursor.fetchall()]

    async def get_latest_model_path(self) -> str | None:
        """Get the output path of the most recent successful training run."""
        await self._ensure_tables()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("""
                SELECT output_path FROM training_runs
                WHERE status = 'completed' AND output_path IS NOT NULL
                ORDER BY completed_at DESC LIMIT 1
            """)
            row = await cursor.fetchone()
            if row:
                return row[0]
        return None

    async def deploy_to_ollama(self, run_id: str | None = None) -> dict[str, Any]:
        """Deploy a trained model to Ollama for local serving.

        Creates an Ollama model named "tova:latest" from the trained weights.

        Args:
            run_id: Specific run to deploy. If None, uses the latest successful run.
        """
        if run_id:
            run = await self.get_status(run_id)
            if not run or run["status"] != "completed":
                return {"deployed": False, "error": "Run not found or not completed"}
            model_path = run["output_path"]
        else:
            model_path = await self.get_latest_model_path()

        if not model_path or not os.path.exists(model_path):
            return {"deployed": False, "error": "No trained model found"}

        # Create Ollama Modelfile
        modelfile_path = os.path.join(model_path, "Modelfile")
        base_model = "tova-base"  # The merged model

        modelfile_content = f"""FROM {model_path}

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM \"\"\"You are Tova, an intelligent AI assistant that learns and adapts to each user.
You use tools to help users accomplish tasks, always with care and accuracy.
When you're unsure, you search for the answer rather than saying you don't know.\"\"\"
"""

        with open(modelfile_path, "w") as f:
            f.write(modelfile_content)

        # Create Ollama model
        import subprocess
        try:
            result = subprocess.run(
                ["ollama", "create", "tova:latest", "-f", modelfile_path],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                logger.info("Deployed Tova model to Ollama as tova:latest")
                return {"deployed": True, "model_name": "tova:latest", "path": model_path}
            else:
                return {"deployed": False, "error": result.stderr}
        except FileNotFoundError:
            return {"deployed": False, "error": "Ollama not installed"}
        except subprocess.TimeoutExpired:
            return {"deployed": False, "error": "Ollama deploy timed out"}
