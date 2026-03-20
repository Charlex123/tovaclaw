"""
Agent definition model — the programmatic equivalent of OpenClaw's SOUL.md + TOOLS.md.

An AgentConfig fully defines an agent: its identity, personality, capabilities,
tools, triggers, and memory settings. Stored in the database (not files),
created via API or dashboard UI.

Usage:
    agent = AgentConfig(
        name="Content Creator",
        description="Generates social media posts across platforms",
        system_prompt="You are a creative social media marketer...",
        tools=["create_post", "list_features", "list_platform_specs"],
        trigger=AgentTrigger(type="manual"),
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TriggerType(str, Enum):
    MANUAL = "manual"         # User triggers via chat
    SCHEDULED = "scheduled"   # Cron-based (HEARTBEAT equivalent)
    EVENT = "event"           # Triggered by another agent or system event


class AgentStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DRAFT = "draft"
    ARCHIVED = "archived"


@dataclass
class AgentTrigger:
    """How and when the agent runs.

    For scheduled triggers, uses cron syntax:
        cron="0 9 * * *"  → every day at 9am
        cron="0 */2 * * *"  → every 2 hours

    For event triggers, listens for named events:
        event="prospect_discovered"
        event="message_approved"
        event="campaign_completed"
    """
    type: TriggerType = TriggerType.MANUAL
    cron: str | None = None            # Cron expression for scheduled triggers
    event: str | None = None           # Event name for event triggers
    timezone: str = "UTC"
    max_runs_per_day: int | None = None


@dataclass
class AgentMemoryConfig:
    """How the agent remembers across conversations.

    max_history: Maximum conversation turns to retain in context
    persist_context: Whether to save extracted context between conversations
    shared_memory: Whether this agent can access other agents' memory
    """
    max_history: int = 20
    persist_context: bool = True
    shared_memory: bool = False


@dataclass
class ToolConfig:
    """Configuration for a tool attached to an agent.

    tool_name: The registered tool name (e.g., "create_post", "find_prospects")
    enabled: Whether the tool is active
    config: Tool-specific configuration overrides
    """
    tool_name: str
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Complete agent definition — the heart of the OpenClaw-style system.

    This replaces:
    - SOUL.md → system_prompt + personality fields
    - TOOLS.md → tools list
    - HEARTBEAT.md → trigger
    - IDENTITY.md → name, description, icon, metadata
    """

    # ── Identity (IDENTITY.md equivalent) ──────────────────────
    id: str = ""
    name: str = ""
    description: str = ""
    icon: str = "bot"           # Icon identifier for UI
    color: str = "brand"        # Color theme for UI
    category: str = "general"   # Grouping: content, outreach, ads, analytics, general

    # ── Personality (SOUL.md equivalent) ───────────────────────
    system_prompt: str = ""     # The agent's core instructions
    personality: str = ""       # Short personality description (warm, professional, etc.)
    greeting: str = ""          # Initial message when conversation starts

    # ── Capabilities (TOOLS.md equivalent) ─────────────────────
    tools: list[ToolConfig] = field(default_factory=list)

    # ── Execution (HEARTBEAT.md equivalent) ────────────────────
    trigger: AgentTrigger = field(default_factory=AgentTrigger)
    max_iterations: int = 15    # Max tool-calling loops per turn
    temperature: float = 0.3
    model_override: str | None = None   # Use a different model than global default
    llm_provider: str | None = None     # Override provider: anthropic, openai, google, local
    llm_api_key: str | None = None      # User's own API key for the selected provider

    # ── Memory ─────────────────────────────────────────────────
    memory: AgentMemoryConfig = field(default_factory=AgentMemoryConfig)

    # ── Workflow (optional multi-step definition) ──────────────
    workflow: list[dict[str, Any]] = field(default_factory=list)

    # ── Metadata ───────────────────────────────────────────────
    status: AgentStatus = AgentStatus.ACTIVE
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1

    def get_tool_names(self) -> list[str]:
        """Get list of enabled tool names."""
        return [t.tool_name for t in self.tools if t.enabled]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "category": self.category,
            "system_prompt": self.system_prompt,
            "personality": self.personality,
            "greeting": self.greeting,
            "tools": [
                {"tool_name": t.tool_name, "enabled": t.enabled, "config": t.config}
                for t in self.tools
            ],
            "trigger": {
                "type": self.trigger.type.value,
                "cron": self.trigger.cron,
                "event": self.trigger.event,
                "timezone": self.trigger.timezone,
                "max_runs_per_day": self.trigger.max_runs_per_day,
            },
            "max_iterations": self.max_iterations,
            "temperature": self.temperature,
            "model_override": self.model_override,
            "llm_provider": self.llm_provider,
            "memory": {
                "max_history": self.memory.max_history,
                "persist_context": self.memory.persist_context,
                "shared_memory": self.memory.shared_memory,
            },
            "workflow": self.workflow,
            "status": self.status.value,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfig:
        """Deserialize from stored dict."""
        tools = [
            ToolConfig(
                tool_name=t["tool_name"],
                enabled=t.get("enabled", True),
                config=t.get("config", {}),
            )
            for t in data.get("tools", [])
        ]

        trigger_data = data.get("trigger", {})
        trigger = AgentTrigger(
            type=TriggerType(trigger_data.get("type", "manual")),
            cron=trigger_data.get("cron"),
            event=trigger_data.get("event"),
            timezone=trigger_data.get("timezone", "UTC"),
            max_runs_per_day=trigger_data.get("max_runs_per_day"),
        )

        memory_data = data.get("memory", {})
        memory = AgentMemoryConfig(
            max_history=memory_data.get("max_history", 20),
            persist_context=memory_data.get("persist_context", True),
            shared_memory=memory_data.get("shared_memory", False),
        )

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            icon=data.get("icon", "bot"),
            color=data.get("color", "brand"),
            category=data.get("category", "general"),
            system_prompt=data.get("system_prompt", ""),
            personality=data.get("personality", ""),
            greeting=data.get("greeting", ""),
            tools=tools,
            trigger=trigger,
            max_iterations=data.get("max_iterations", 15),
            temperature=data.get("temperature", 0.3),
            model_override=data.get("model_override"),
            llm_provider=data.get("llm_provider"),
            llm_api_key=data.get("llm_api_key"),
            memory=memory,
            workflow=data.get("workflow", []),
            status=AgentStatus(data.get("status", "active")),
            created_by=data.get("created_by", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
            version=data.get("version", 1),
        )
