"""
Agent memory system — persistent context across conversations.

Unlike conversation history (which stores raw messages), memory stores
extracted facts, preferences, and context that agents carry forward.

This is the equivalent of OpenClaw's memory system, but using the
existing BaseStore interface instead of SQLite vectors.

Usage:
    memory = AgentMemory(store)

    # Save a memory entry
    await memory.save(agent_id="agent_1", key="user_preference", value="likes casual tone")

    # Load all memories for an agent
    memories = await memory.load(agent_id="agent_1")

    # Build context string for system prompt injection
    context = await memory.build_context(agent_id="agent_1")
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


class AgentMemory:
    """Persistent memory layer for agents.

    Stores key-value facts that persist across conversations.
    The runtime injects these into the system prompt as context.
    """

    def __init__(self, store: BaseStore):
        self.store = store

    async def save(
        self,
        agent_id: str,
        key: str,
        value: str,
        category: str = "general",
        source: str = "agent",
    ) -> None:
        """Save or update a memory entry.

        Args:
            agent_id: Which agent owns this memory
            key: Memory key (e.g., "user_name", "preferred_tone")
            value: The remembered value
            category: Memory category (user, product, preference, fact)
            source: Who created it (agent, user, system)
        """
        try:
            await self.store.save_agent_memory(
                agent_id=agent_id,
                key=key,
                value=value,
                category=category,
                source=source,
                timestamp=datetime.now().isoformat(),
            )
        except NotImplementedError:
            logger.debug("Agent memory persistence not implemented in store")
        except Exception as e:
            logger.warning(f"Failed to save agent memory: {e}")

    async def load(self, agent_id: str, category: str | None = None) -> list[dict[str, Any]]:
        """Load all memories for an agent, optionally filtered by category."""
        try:
            return await self.store.load_agent_memories(agent_id, category=category)
        except NotImplementedError:
            return []
        except Exception as e:
            logger.warning(f"Failed to load agent memories: {e}")
            return []

    async def delete(self, agent_id: str, key: str) -> None:
        """Delete a specific memory entry."""
        try:
            await self.store.delete_agent_memory(agent_id, key)
        except NotImplementedError:
            pass
        except Exception as e:
            logger.warning(f"Failed to delete agent memory: {e}")

    async def clear(self, agent_id: str) -> None:
        """Clear all memories for an agent."""
        try:
            await self.store.clear_agent_memories(agent_id)
        except NotImplementedError:
            pass
        except Exception as e:
            logger.warning(f"Failed to clear agent memories: {e}")

    async def build_context(self, agent_id: str) -> str:
        """Build a context string from memories for system prompt injection.

        Returns a formatted string like:
            ## Remembered Context
            - user_name: John
            - preferred_tone: casual
            - last_campaign: Q1 product launch
        """
        memories = await self.load(agent_id)
        if not memories:
            return ""

        lines = ["## Remembered Context"]
        for mem in memories:
            lines.append(f"- {mem.get('key', '?')}: {mem.get('value', '')}")

        return "\n".join(lines)
