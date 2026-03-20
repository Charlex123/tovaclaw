"""
Pluggable tool system — replaces hardcoded tool registries.

Instead of one monolithic build_order_tools(), products register their own
tools via ToolRegistry. Agents select which tools they can use.

Usage:
    registry = ToolRegistry()

    # Register tools from your product
    registry.register(ToolDefinition(
        name="create_post",
        description="Generate a social media post",
        category="content",
        handler=my_create_post_handler,
        parameters={...},
    ))

    # Build tools for a specific agent (only its selected tools)
    agent_tools = registry.build_tools(agent_config)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from langchain_core.tools import tool as langchain_tool, BaseTool

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    """Describes a single parameter for a tool."""
    name: str
    type: str = "string"           # string, number, boolean, array, object
    description: str = ""
    required: bool = False
    default: Any = None
    enum: list[str] | None = None  # For restricted choices


@dataclass
class ToolDefinition:
    """A tool that can be attached to any agent.

    This is the framework's equivalent of OpenClaw's SKILL.md.
    Each tool is a self-contained capability that agents can use.

    handler: An async function that implements the tool's logic.
             Signature: async def handler(**kwargs) -> dict
    """
    name: str
    description: str
    category: str = "general"      # content, outreach, ads, analytics, data, social, general
    handler: Callable[..., Awaitable[dict]] | None = None
    parameters: list[ToolParameter] = field(default_factory=list)
    requires_auth: bool = False
    requires_backend: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    # Pre-built LangChain tool (alternative to handler)
    _langchain_tool: BaseTool | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses (without handler)."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "enum": p.enum,
                }
                for p in self.parameters
            ],
            "requires_auth": self.requires_auth,
            "requires_backend": self.requires_backend,
            "metadata": self.metadata,
        }


class ToolRegistry:
    """Central registry of all available tools.

    Products register their tools here. Agents pick which tools they use.
    The runtime builds the final LangChain tool list from the agent's selection.

    This replaces the hardcoded build_order_tools() / build_execution_tools().
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool_def: ToolDefinition) -> None:
        """Register a tool definition."""
        if tool_def.name in self._tools:
            logger.warning(f"Tool '{tool_def.name}' already registered, overwriting")
        self._tools[tool_def.name] = tool_def
        logger.debug(f"Registered tool: {tool_def.name} [{tool_def.category}]")

    def register_langchain_tool(
        self,
        lc_tool: BaseTool,
        category: str = "general",
        requires_auth: bool = False,
        requires_backend: bool = False,
    ) -> None:
        """Register a pre-built LangChain @tool function.

        This allows existing LangChain tools (like the built-in tools
        from build_order_tools) to work with the new registry system.
        """
        tool_def = ToolDefinition(
            name=lc_tool.name,
            description=lc_tool.description or "",
            category=category,
            requires_auth=requires_auth,
            requires_backend=requires_backend,
            _langchain_tool=lc_tool,
        )
        self.register(tool_def)

    def register_many(self, tool_defs: list[ToolDefinition]) -> None:
        """Register multiple tools at once."""
        for td in tool_defs:
            self.register(td)

    def register_langchain_tools(
        self,
        lc_tools: list[BaseTool],
        category: str = "general",
    ) -> None:
        """Register a list of pre-built LangChain tools."""
        for t in lc_tools:
            self.register_langchain_tool(t, category=category)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool definition by name."""
        return self._tools.get(name)

    def list_all(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_by_category(self, category: str) -> list[ToolDefinition]:
        """List tools in a specific category."""
        return [t for t in self._tools.values() if t.category == category]

    def get_categories(self) -> list[str]:
        """Get all unique tool categories."""
        return sorted(set(t.category for t in self._tools.values()))

    def build_langchain_tools(self, tool_names: list[str]) -> list[BaseTool]:
        """Build LangChain tool instances for the given tool names.

        This is what the agent runtime calls to get the tools for a specific agent.
        Only tools in the agent's selected list are included.
        """
        lc_tools = []

        for name in tool_names:
            tool_def = self._tools.get(name)
            if not tool_def:
                logger.warning(f"Tool '{name}' not found in registry, skipping")
                continue

            # If it's already a LangChain tool, use it directly
            if tool_def._langchain_tool is not None:
                lc_tools.append(tool_def._langchain_tool)
                continue

            # Otherwise, wrap the handler as a LangChain tool
            if tool_def.handler is not None:
                handler = tool_def.handler
                desc = tool_def.description

                @langchain_tool(name=name, description=desc)
                async def _wrapped(**kwargs) -> dict:
                    return await handler(**kwargs)

                lc_tools.append(_wrapped)
            else:
                logger.warning(f"Tool '{name}' has no handler or LangChain tool, skipping")

        return lc_tools

    def to_catalog(self) -> list[dict[str, Any]]:
        """Export the full tool catalog for API responses / UI rendering."""
        categories = {}
        for tool_def in self._tools.values():
            cat = tool_def.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tool_def.to_dict())

        return [
            {"category": cat, "tools": tools}
            for cat, tools in sorted(categories.items())
        ]
