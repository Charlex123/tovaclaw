"""
Training Data Generator — converts Tova interactions into fine-tuning samples.

Generates multiple training formats from real usage:
1. Chat completion pairs (instruction → response)
2. Tool-calling examples (function call format)
3. Reasoning chains (for training thinking behavior)
4. Preference pairs (chosen vs rejected for DPO/RLHF)
5. Domain-specific Q&A from Brain Box memories

All data passes through the consent + anonymization pipeline before storage.
Samples are stored in SQLite for reproducibility and auditability.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import aiosqlite

from tova_core.training.consent import (
    ConsentManager,
    DataScope,
    anonymize_sample,
    hash_user_id,
)
from tova_core.config import get_settings

logger = logging.getLogger(__name__)


class SampleFormat(str):
    """Training sample formats."""
    CHAT = "chat"  # {"messages": [{"role": ..., "content": ...}]}
    TOOL_CALL = "tool_call"  # Chat + tool_calls field
    REASONING = "reasoning"  # Chat with <think> tags in assistant response
    PREFERENCE = "preference"  # {"chosen": ..., "rejected": ...} for DPO
    QA = "qa"  # {"question": ..., "answer": ...}


class TrainingDataGenerator:
    """Generates and stores training samples from Tova interactions.

    The generator sits between the learning engine and the fine-tuning pipeline.
    It collects high-quality conversation samples, anonymizes them, and stores
    them in a format ready for LoRA/QLoRA fine-tuning.

    Lifecycle:
        1. Agent runtime calls `maybe_collect()` after each turn
        2. Consent is checked — if not granted, nothing is stored
        3. PII is stripped from the conversation
        4. Sample is formatted and stored in SQLite
        5. When enough samples accumulate, fine-tuning can be triggered
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or self._default_db_path()
        self._consent = ConsentManager(db_path)
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
                CREATE TABLE IF NOT EXISTS training_samples (
                    id TEXT PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    format TEXT NOT NULL,
                    sample_data TEXT NOT NULL,
                    quality_score REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    source TEXT DEFAULT 'interaction',
                    metadata TEXT DEFAULT '{}',
                    used_in_training INTEGER DEFAULT 0,
                    training_run_id TEXT DEFAULT NULL
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_samples_user
                ON training_samples(user_hash)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_samples_format
                ON training_samples(format)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_samples_quality
                ON training_samples(quality_score DESC)
            """)
            await db.commit()
        self._initialized = True

    # ── Collection from Interactions ──────────────────────────────────

    async def maybe_collect(
        self,
        user_id: str,
        user_message: str,
        agent_reply: str,
        system_prompt: str = "",
        tools_used: list[str] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        thinking: str = "",
        conversation_history: list[dict[str, str]] | None = None,
        quality_signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Collect a training sample if consent is granted.

        Called after each agent turn. Checks consent, anonymizes, scores
        quality, and stores the sample.

        Args:
            user_id: The user whose interaction this is.
            user_message: What the user said.
            agent_reply: What Tova responded.
            system_prompt: The system prompt used (for full context).
            tools_used: Tool names that were called.
            tool_calls: Full tool call details (name, args, result).
            thinking: Chain-of-thought reasoning (if reasoning model used).
            conversation_history: Prior messages for multi-turn context.
            quality_signals: Signals for scoring sample quality.

        Returns:
            {"collected": bool, "sample_id": str | None, "reason": str}
        """
        # Check consent
        if not await self._consent.is_collection_allowed(user_id, DataScope.CONVERSATIONS):
            return {"collected": False, "sample_id": None, "reason": "no_consent"}

        settings = get_settings()

        # Score quality — skip low-quality samples
        quality = self._score_quality(
            user_message, agent_reply, tools_used or [], quality_signals or {},
        )
        if quality < 0.3:
            return {"collected": False, "sample_id": None, "reason": "low_quality"}

        # Generate samples (may produce multiple formats from one interaction)
        samples = []

        # 1. Chat completion sample
        chat_sample = self._build_chat_sample(
            user_message, agent_reply, system_prompt, conversation_history,
        )
        samples.append((SampleFormat.CHAT, chat_sample, quality))

        # 2. Tool-calling sample (if tools were used)
        if tool_calls:
            tool_sample = self._build_tool_call_sample(
                user_message, agent_reply, system_prompt, tool_calls,
            )
            samples.append((SampleFormat.TOOL_CALL, tool_sample, quality + 0.1))

        # 3. Reasoning sample (if thinking was produced)
        if thinking:
            reasoning_sample = self._build_reasoning_sample(
                user_message, agent_reply, system_prompt, thinking,
            )
            samples.append((SampleFormat.REASONING, reasoning_sample, quality + 0.15))

        # Anonymize and store
        user_hash = hash_user_id(user_id)
        stored_ids = []

        for fmt, sample, score in samples:
            if settings.data_anonymize_pii:
                sample = anonymize_sample(sample)

            sample_id = await self._store_sample(user_hash, fmt, sample, score)
            stored_ids.append(sample_id)

        return {
            "collected": True,
            "sample_ids": stored_ids,
            "formats": [s[0] for s in samples],
            "quality_score": quality,
        }

    async def collect_correction(
        self,
        user_id: str,
        original_response: str,
        corrected_response: str,
        user_message: str,
        system_prompt: str = "",
    ) -> dict[str, Any]:
        """Collect a preference pair from a user correction.

        When users correct Tova, that's a gold-standard signal for DPO training:
        the original is "rejected" and the correction is "chosen".
        """
        if not await self._consent.is_collection_allowed(user_id, DataScope.CORRECTIONS):
            return {"collected": False, "reason": "no_consent"}

        settings = get_settings()

        preference_sample = {
            "prompt": user_message,
            "system": system_prompt,
            "chosen": corrected_response,
            "rejected": original_response,
        }

        if settings.data_anonymize_pii:
            preference_sample = anonymize_sample(preference_sample)

        user_hash = hash_user_id(user_id)
        sample_id = await self._store_sample(
            user_hash, SampleFormat.PREFERENCE, preference_sample,
            quality_score=1.0,  # corrections are highest quality
            source="correction",
        )

        return {"collected": True, "sample_id": sample_id, "format": "preference"}

    async def collect_from_brain_box(
        self,
        user_id: str,
        feature: str,
        memories: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Generate Q&A training samples from Brain Box memories.

        Converts stored knowledge into question-answer pairs, enriching the
        training set with domain-specific information.
        """
        if not await self._consent.is_collection_allowed(user_id, DataScope.PREFERENCES):
            return {"collected": False, "reason": "no_consent"}

        settings = get_settings()
        user_hash = hash_user_id(user_id)
        count = 0

        for memory in memories:
            key = memory.get("key", "")
            value = memory.get("value", "")
            category = memory.get("category", "fact")

            if not key or not value:
                continue

            # Generate a natural question-answer pair
            qa_sample = self._memory_to_qa(key, value, category, feature)
            if qa_sample:
                if settings.data_anonymize_pii:
                    qa_sample = anonymize_sample(qa_sample)

                await self._store_sample(
                    user_hash, SampleFormat.QA, qa_sample,
                    quality_score=0.7,
                    source="brain_box",
                )
                count += 1

        return {"collected": True, "samples_generated": count}

    # ── Sample Building ───────────────────────────────────────────────

    def _build_chat_sample(
        self,
        user_message: str,
        agent_reply: str,
        system_prompt: str,
        history: list[dict[str, str]] | None,
    ) -> dict[str, Any]:
        """Build a chat-format training sample."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            for msg in history[-6:]:  # last 3 turns for context
                messages.append(msg)

        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "assistant", "content": agent_reply})

        return {"messages": messages}

    def _build_tool_call_sample(
        self,
        user_message: str,
        agent_reply: str,
        system_prompt: str,
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a tool-calling training sample.

        Format follows OpenAI function calling convention for compatibility
        with most fine-tuning frameworks.
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": user_message})

        # Assistant message with tool calls
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": ""}
        formatted_calls = []
        for tc in tool_calls:
            formatted_calls.append({
                "id": tc.get("id", f"call_{uuid4().hex[:8]}"),
                "type": "function",
                "function": {
                    "name": tc.get("name", "unknown"),
                    "arguments": json.dumps(tc.get("args", {})),
                },
            })
        assistant_msg["tool_calls"] = formatted_calls
        messages.append(assistant_msg)

        # Tool responses
        for tc in tool_calls:
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": json.dumps(tc.get("result", ""), default=str),
            })

        # Final assistant response
        messages.append({"role": "assistant", "content": agent_reply})

        return {"messages": messages}

    def _build_reasoning_sample(
        self,
        user_message: str,
        agent_reply: str,
        system_prompt: str,
        thinking: str,
    ) -> dict[str, Any]:
        """Build a reasoning training sample with thinking tokens."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": user_message})

        # Assistant response with thinking wrapped in tags
        response_with_thinking = f"<think>\n{thinking}\n</think>\n\n{agent_reply}"
        messages.append({"role": "assistant", "content": response_with_thinking})

        return {"messages": messages}

    def _memory_to_qa(
        self,
        key: str,
        value: str,
        category: str,
        feature: str,
    ) -> dict[str, Any] | None:
        """Convert a Brain Box memory entry into a Q&A training sample."""
        # Generate contextual questions based on category
        question_templates = {
            "preference": f"What is the user's preference for {key.replace('_', ' ')}?",
            "fact": f"What do you know about {key.replace('_', ' ')}?",
            "pattern": f"What is the user's typical pattern for {key.replace('_', ' ')}?",
            "correction": f"What was corrected about {key.replace('_', ' ')}?",
            "entity": f"Who or what is {key.replace('entity_', '').replace('_', ' ')}?",
        }

        question = question_templates.get(category)
        if not question:
            return None

        return {
            "question": question,
            "answer": value,
            "context": f"Feature: {feature}, Category: {category}",
        }

    # ── Quality Scoring ───────────────────────────────────────────────

    def _score_quality(
        self,
        user_message: str,
        agent_reply: str,
        tools_used: list[str],
        signals: dict[str, Any],
    ) -> float:
        """Score the quality of an interaction for training purposes.

        Higher quality samples are more valuable for fine-tuning.

        Returns 0.0 to 1.0.
        """
        score = 0.5  # baseline

        # Message length — too short = low quality
        if len(user_message) < 10:
            score -= 0.2
        elif len(user_message) > 50:
            score += 0.1

        # Response quality
        if len(agent_reply) < 20:
            score -= 0.2
        elif len(agent_reply) > 100:
            score += 0.1

        # Tool usage = more informative interaction
        if tools_used:
            score += 0.15
        if len(tools_used) > 2:
            score += 0.1

        # External quality signals
        if signals.get("user_satisfied"):
            score += 0.2
        if signals.get("user_corrected"):
            score -= 0.1  # correction = the original response was wrong
        if signals.get("task_completed"):
            score += 0.15

        # Penalize greetings and chitchat (low training value)
        msg_lower = user_message.lower().strip()
        if msg_lower in ("hi", "hello", "hey", "thanks", "thank you", "ok", "bye"):
            score -= 0.3

        return max(0.0, min(1.0, score))

    # ── Storage ───────────────────────────────────────────────────────

    async def _store_sample(
        self,
        user_hash: str,
        fmt: str,
        sample: dict[str, Any],
        quality_score: float,
        source: str = "interaction",
    ) -> str:
        """Store a training sample in SQLite."""
        await self._ensure_tables()
        sample_id = uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO training_samples (id, user_hash, format, sample_data, quality_score, created_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sample_id, user_hash, fmt, json.dumps(sample), quality_score, now, source))
            await db.commit()

        return sample_id

    async def get_sample_count(self, min_quality: float = 0.0) -> int:
        """Get the total number of training samples."""
        await self._ensure_tables()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM training_samples WHERE quality_score >= ?",
                (min_quality,),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def export_training_set(
        self,
        fmt: str | None = None,
        min_quality: float = 0.5,
        limit: int = 0,
        exclude_used: bool = False,
    ) -> list[dict[str, Any]]:
        """Export training samples for fine-tuning.

        Args:
            fmt: Filter by format (chat, tool_call, reasoning, preference, qa).
            min_quality: Minimum quality score.
            limit: Max samples to export (0 = all).
            exclude_used: Skip samples already used in a training run.

        Returns:
            List of training samples ready for the fine-tuning pipeline.
        """
        await self._ensure_tables()
        query = "SELECT * FROM training_samples WHERE quality_score >= ?"
        params: list[Any] = [min_quality]

        if fmt:
            query += " AND format = ?"
            params.append(fmt)

        if exclude_used:
            query += " AND used_in_training = 0"

        query += " ORDER BY quality_score DESC"

        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "format": row["format"],
                    "data": json.loads(row["sample_data"]),
                    "quality_score": row["quality_score"],
                    "source": row["source"],
                }
                for row in rows
            ]

    async def mark_samples_used(self, sample_ids: list[str], training_run_id: str) -> None:
        """Mark samples as used in a training run."""
        await self._ensure_tables()
        async with aiosqlite.connect(self._db_path) as db:
            placeholders = ",".join("?" * len(sample_ids))
            await db.execute(f"""
                UPDATE training_samples
                SET used_in_training = 1, training_run_id = ?
                WHERE id IN ({placeholders})
            """, [training_run_id] + sample_ids)
            await db.commit()

    async def cleanup_expired(self) -> int:
        """Delete training samples older than the retention period."""
        settings = get_settings()
        if settings.data_retention_days <= 0:
            return 0

        from datetime import timedelta
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=settings.data_retention_days)
        ).isoformat()

        await self._ensure_tables()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM training_samples WHERE created_at < ?", (cutoff,)
            )
            await db.commit()
            return cursor.rowcount

    async def get_stats(self) -> dict[str, Any]:
        """Get statistics about the training dataset."""
        await self._ensure_tables()
        async with aiosqlite.connect(self._db_path) as db:
            # Total count
            cursor = await db.execute("SELECT COUNT(*) FROM training_samples")
            total = (await cursor.fetchone())[0]

            # Count by format
            cursor = await db.execute(
                "SELECT format, COUNT(*) FROM training_samples GROUP BY format"
            )
            by_format = {row[0]: row[1] for row in await cursor.fetchall()}

            # Average quality
            cursor = await db.execute(
                "SELECT AVG(quality_score) FROM training_samples"
            )
            avg_quality = (await cursor.fetchone())[0] or 0.0

            # Unused count (available for next training)
            cursor = await db.execute(
                "SELECT COUNT(*) FROM training_samples WHERE used_in_training = 0"
            )
            unused = (await cursor.fetchone())[0]

            settings = get_settings()

            return {
                "total_samples": total,
                "by_format": by_format,
                "average_quality": round(avg_quality, 3),
                "unused_samples": unused,
                "min_for_training": settings.tova_training_min_samples,
                "ready_for_training": unused >= settings.tova_training_min_samples,
            }
