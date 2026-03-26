"""
Brain Box — per-feature, per-user memory namespace.

Each feature (email, todos, cctv, emergency, etc.) gets its own isolated
memory space for every user. This enables personalized context without
cross-contamination between features.

Usage:
    box = BrainBox(store, "todos")

    # Remember something for a user
    await box.remember("user_123", "preferred_priority", "high", category="preference")

    # Recall all memories for a user
    memories = await box.recall("user_123")

    # Build context string for system prompt injection
    context = await box.build_context("user_123")

    # Share a memory to another feature
    await box.share_to("user_123", "events", ["preferred_priority"])
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


class BrainBox:
    """Per-feature, per-user memory namespace.

    Each brain box is scoped to a single feature (e.g., "todos", "email", "cctv").
    All memories within a brain box are isolated to a specific user.

    Namespace key pattern: brain_{feature}_{user_id}
    """

    def __init__(self, store: BaseStore, feature: str):
        self.store = store
        self.feature = feature

    def _namespace(self, user_id: str) -> str:
        """Generate a unique namespace key for this feature + user."""
        return f"brain_{self.feature}_{user_id}"

    async def remember(
        self,
        user_id: str,
        key: str,
        value: str,
        category: str = "fact",
        ttl_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Save a memory entry to this brain box.

        Args:
            user_id: The user who owns this memory
            key: Memory key (e.g., "preferred_email_sort", "last_emergency_type")
            value: The remembered value
            category: One of: user, preference, fact, context, history
            ttl_days: Optional expiration in days (None = never expires)
            metadata: Additional metadata to store with the memory
        """
        namespace = self._namespace(user_id)
        now = datetime.now().isoformat()
        expires_at = None
        if ttl_days is not None:
            expires_at = (
                datetime.fromtimestamp(time.time() + ttl_days * 86400).isoformat()
            )

        try:
            await self.store.save_brain_memory(
                namespace=namespace,
                key=key,
                value=value,
                category=category,
                metadata={
                    **(metadata or {}),
                    "feature": self.feature,
                    "relevance_score": 1.0,
                    "created_at": now,
                    "updated_at": now,
                    "expires_at": expires_at,
                },
            )
        except NotImplementedError:
            logger.debug(f"Brain memory persistence not implemented for {self.feature}")
        except Exception as e:
            logger.warning(f"Failed to save brain memory [{self.feature}]: {e}")

    async def recall(
        self,
        user_id: str,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recall all memories for this user in this brain box.

        Args:
            user_id: The user to recall for
            category: Optional filter by category

        Returns:
            List of memory dicts with: key, value, category, metadata
        """
        namespace = self._namespace(user_id)
        try:
            memories = await self.store.load_brain_memories(
                namespace=namespace, category=category
            )
            # Filter out expired memories
            now = datetime.now().isoformat()
            return [
                m for m in memories
                if not m.get("metadata", {}).get("expires_at")
                or m["metadata"]["expires_at"] > now
            ]
        except NotImplementedError:
            return []
        except Exception as e:
            logger.warning(f"Failed to recall brain memories [{self.feature}]: {e}")
            return []

    async def recall_relevant(
        self,
        user_id: str,
        query: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Recall memories relevant to a query using keyword matching.

        Falls back to simple keyword matching. If a vector store is available
        externally, the caller should use that instead.

        Args:
            user_id: The user to recall for
            query: Natural language query
            top_k: Maximum number of results

        Returns:
            List of memory dicts sorted by relevance
        """
        memories = await self.recall(user_id)
        if not memories:
            return []

        # Simple keyword relevance scoring
        query_words = set(query.lower().split())
        scored = []
        for mem in memories:
            text = f"{mem.get('key', '')} {mem.get('value', '')}".lower()
            overlap = sum(1 for w in query_words if w in text)
            base_score = mem.get("metadata", {}).get("relevance_score", 0.5)
            score = overlap * 0.3 + base_score * 0.7
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:top_k]]

    async def build_context(self, user_id: str) -> str:
        """Build a context string from memories for system prompt injection.

        Returns a formatted section like:
            ## {Feature} Context
            - preferred_sort: by_priority
            - last_viewed_folder: inbox
        """
        memories = await self.recall(user_id)
        if not memories:
            return ""

        feature_title = self.feature.replace("_", " ").title()
        lines = [f"## {feature_title} Memory"]
        for mem in memories:
            key = mem.get("key", "?")
            value = mem.get("value", "")
            lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    async def forget(self, user_id: str, key: str) -> None:
        """Delete a specific memory entry."""
        namespace = self._namespace(user_id)
        try:
            await self.store.delete_brain_memory(namespace, key)
        except NotImplementedError:
            pass
        except Exception as e:
            logger.warning(f"Failed to delete brain memory [{self.feature}]: {e}")

    async def clear(self, user_id: str) -> None:
        """Clear all memories for this user in this brain box."""
        namespace = self._namespace(user_id)
        try:
            await self.store.clear_brain_namespace(namespace)
        except NotImplementedError:
            pass
        except Exception as e:
            logger.warning(f"Failed to clear brain box [{self.feature}]: {e}")

    async def decay(self, user_id: str, decay_factor: float = 0.95) -> None:
        """Reduce relevance scores of memories (time-based decay).

        Older memories naturally become less relevant. Call this periodically
        (e.g., daily) to let recent memories dominate.
        """
        memories = await self.recall(user_id)
        namespace = self._namespace(user_id)
        for mem in memories:
            current_score = mem.get("metadata", {}).get("relevance_score", 1.0)
            new_score = max(0.01, current_score * decay_factor)
            try:
                await self.store.save_brain_memory(
                    namespace=namespace,
                    key=mem["key"],
                    value=mem["value"],
                    category=mem.get("category", "fact"),
                    metadata={
                        **mem.get("metadata", {}),
                        "relevance_score": new_score,
                        "updated_at": datetime.now().isoformat(),
                    },
                )
            except (NotImplementedError, Exception):
                pass

    async def share_to(
        self,
        user_id: str,
        target_feature: str,
        keys: list[str],
    ) -> None:
        """Share specific memories to another feature's brain box.

        Args:
            user_id: The user whose memories to share
            target_feature: The feature to share to
            keys: List of memory keys to share
        """
        memories = await self.recall(user_id)
        target_box = BrainBox(self.store, target_feature)

        for mem in memories:
            if mem.get("key") in keys:
                await target_box.remember(
                    user_id=user_id,
                    key=mem["key"],
                    value=mem["value"],
                    category=mem.get("category", "fact"),
                    metadata={
                        **(mem.get("metadata", {})),
                        "shared_from": self.feature,
                    },
                )
