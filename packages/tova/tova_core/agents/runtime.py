"""
Generic Agent Runtime — runs any agent defined by AgentConfig.

This is the OpenClaw PiEmbeddedRunner equivalent. Unlike order_agent.py
(which is hardcoded for healthcare), this runtime works with any tools
and any system prompt.

Usage:
    runtime = AgentRuntime(tool_registry=registry, store=store)
    result = await runtime.run(
        agent_config=my_agent,
        user_message="Create a Facebook post about our new feature",
        user_id="user_123",
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tova_core.llm import build_llm
from tova_core.models.agent import AgentConfig
from tova_core.tools.base import ToolRegistry
from tova_core.providers.store import BaseStore
from tova_core.memory.brain_box import BrainBox
from tova_core.learning.engine import SelfLearner

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Executes agents dynamically based on their AgentConfig.

    The runtime:
    1. Loads the agent's system prompt and personality
    2. Builds the tool set from the agent's selected tools
    3. Runs a LangGraph ReAct loop
    4. Persists conversation memory
    5. Returns structured results
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        store: BaseStore,
        self_learner: SelfLearner | None = None,
    ):
        self.tool_registry = tool_registry
        self.store = store
        self.self_learner = self_learner or SelfLearner()
        self._checkpointers: dict[str, MemorySaver] = {}

    def _get_checkpointer(self, agent_id: str) -> MemorySaver:
        """Get or create a memory checkpointer for an agent."""
        if agent_id not in self._checkpointers:
            self._checkpointers[agent_id] = MemorySaver()
        return self._checkpointers[agent_id]

    def _build_system_prompt(self, agent: AgentConfig, context: dict | None = None) -> str:
        """Assemble the full system prompt from agent config + context."""
        parts = []

        # Core identity
        if agent.system_prompt:
            parts.append(agent.system_prompt)
        else:
            parts.append(
                f"You are {agent.name}, an AI assistant.\n"
                f"{agent.description}\n"
            )

        # Personality
        if agent.personality:
            parts.append(f"\n## Personality\n{agent.personality}")

        # Available tools description
        tool_names = agent.get_tool_names()
        if tool_names:
            tool_descriptions = []
            for name in tool_names:
                tool_def = self.tool_registry.get(name)
                if tool_def:
                    tool_descriptions.append(f"- {name}: {tool_def.description}")
            if tool_descriptions:
                parts.append(
                    "\n## Your Tools\n"
                    "You have access to these tools. Use them to help the user:\n"
                    + "\n".join(tool_descriptions)
                )

        # Injected context
        if context:
            ctx_lines = [f"- {k}: {v}" for k, v in context.items() if v]
            if ctx_lines:
                parts.append("\n## Current Context\n" + "\n".join(ctx_lines))

        # Workflow instructions
        if agent.workflow:
            steps = []
            for step in agent.workflow:
                step_num = step.get("step", "?")
                step_name = step.get("name", "")
                step_desc = step.get("description", "")
                steps.append(f"{step_num}. **{step_name}** — {step_desc}")
            parts.append(
                "\n## Workflow\nFollow these steps in order:\n" + "\n".join(steps)
            )

        # Core rules
        parts.append(
            "\n## Rules\n"
            "- Be concise and helpful\n"
            "- Use tools when you need to take action, don't just describe what you would do\n"
            "- If you need more information, ask ONE specific question\n"
            "- Remember context from the conversation — don't re-ask what you already know\n"
            "- When presenting options, be clear and organized"
        )

        return "\n".join(parts)

    async def run(
        self,
        agent_config: AgentConfig,
        user_message: str,
        user_id: str = "",
        conversation_id: str | None = None,
        context: dict | None = None,
        auth_token: str | None = None,
    ) -> dict:
        """Run a single turn of an agent conversation.

        Args:
            agent_config: The agent definition
            user_message: User's input message
            user_id: User identifier
            conversation_id: Thread ID for continuity (generated if None)
            context: Additional context to inject into the system prompt
            auth_token: Optional auth token for tool calls

        Returns:
            dict with: reply, action, conversation_id, tools_used, data
        """
        is_new = not conversation_id
        if not conversation_id:
            conversation_id = await self.store.generate_id()

        # Build tools from agent's selection
        tool_names = agent_config.get_tool_names()
        lc_tools = self.tool_registry.build_langchain_tools(tool_names)

        if not lc_tools:
            logger.warning(f"Agent '{agent_config.name}' has no valid tools")

        # Build system prompt
        full_context = dict(context or {})
        if user_id:
            full_context["user_id"] = user_id
        if auth_token:
            full_context["auth_token"] = auth_token

        system_prompt = self._build_system_prompt(agent_config, full_context)

        # Inject Brain Box context for each declared feature
        if agent_config.brain_boxes and user_id:
            brain_context_parts = []
            for feature_name in agent_config.brain_boxes:
                try:
                    box = BrainBox(self.store, feature_name)
                    ctx = await box.build_context(user_id)
                    if ctx:
                        brain_context_parts.append(ctx)
                except Exception as e:
                    logger.debug(f"Brain box '{feature_name}' context error: {e}")
            if brain_context_parts:
                system_prompt += "\n\n" + "\n\n".join(brain_context_parts)

        # Build LLM (with per-agent provider/model/key overrides)
        llm = build_llm(
            model_override=agent_config.model_override,
            provider_override=agent_config.llm_provider,
            api_key_override=agent_config.llm_api_key,
            temperature=agent_config.temperature,
        )

        # Build ReAct agent
        checkpointer = self._get_checkpointer(agent_config.id or "default")
        agent = create_react_agent(
            model=llm,
            tools=lc_tools,
            prompt=system_prompt,
            checkpointer=checkpointer,
        )

        config = {"configurable": {"thread_id": conversation_id}}

        # Greeting for new conversations
        if is_new and agent_config.greeting:
            greeting_msg = agent_config.greeting
        else:
            greeting_msg = None

        # Run agent
        try:
            result = await agent.ainvoke(
                {"messages": [("human", user_message)]},
                config=config,
            )
        except Exception as e:
            if "INVALID_CHAT_HISTORY" in str(e) or "tool_calls" in str(e):
                logger.warning(f"Corrupted history for agent '{agent_config.name}', starting fresh")
                conversation_id = await self.store.generate_id()
                config = {"configurable": {"thread_id": conversation_id}}
                try:
                    result = await agent.ainvoke(
                        {"messages": [("human", user_message)]},
                        config=config,
                    )
                except Exception as retry_err:
                    logger.error(f"Agent retry failed: {retry_err}")
                    return self._error_response(conversation_id, str(retry_err))
            else:
                logger.error(f"Agent error: {e}")
                return self._error_response(conversation_id, str(e))

        # Extract response
        try:
            ai_messages = [m for m in result["messages"] if m.type == "ai" and m.content]
            reply = ai_messages[-1].content if ai_messages else "Done."

            tool_messages = [m for m in result["messages"] if m.type == "tool"]
            tools_used = list({m.name for m in tool_messages})

            # Extract last tool result as structured data
            data = self._extract_data(result["messages"])

            # Prepend greeting for first message
            if greeting_msg and is_new:
                reply = f"{greeting_msg}\n\n{reply}"

            # Persist conversation
            now = datetime.now().isoformat()
            try:
                await self.store.save_conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    messages=[
                        {"role": "user", "content": user_message, "timestamp": now},
                        {"role": "assistant", "content": reply, "tools_used": tools_used, "data": data, "timestamp": now},
                    ],
                    title=user_message[:80],
                )
            except Exception as save_err:
                logger.warning(f"Failed to save conversation: {save_err}")

            # Self-learning: extract knowledge from this turn
            if self.self_learner and user_id:
                try:
                    feature = "general"
                    if agent_config.brain_boxes:
                        feature = agent_config.brain_boxes[0]
                    await self.self_learner.learn_from_turn(
                        user_id=user_id,
                        user_message=user_message,
                        agent_reply=reply,
                        tools_used=tools_used,
                        agent_id=agent_config.id or "",
                        feature=feature,
                        conversation_id=conversation_id,
                    )
                except Exception as learn_err:
                    logger.debug(f"Self-learning extraction failed (non-critical): {learn_err}")

            return {
                "reply": reply,
                "agent_id": agent_config.id,
                "agent_name": agent_config.name,
                "conversation_id": conversation_id,
                "tools_used": tools_used,
                "data": data,
            }

        except Exception as e:
            logger.error(f"Response extraction error: {e}")
            return self._error_response(conversation_id, str(e))

    def _extract_data(self, messages: list) -> dict | None:
        """Extract the last meaningful tool result as structured data."""
        tool_messages = [m for m in messages if m.type == "tool"]
        if not tool_messages:
            return None

        for msg in reversed(tool_messages):
            try:
                if isinstance(msg.content, str):
                    content = json.loads(msg.content)
                elif isinstance(msg.content, dict):
                    content = msg.content
                else:
                    continue
            except (json.JSONDecodeError, TypeError):
                continue

            if isinstance(content, dict):
                return {"tool": msg.name, **content}

        return None

    def _error_response(self, conversation_id: str, error: str) -> dict:
        error_lower = error.lower()
        if "credit balance" in error_lower or "rate_limit" in error_lower:
            reply = "I'm temporarily unavailable. Please try again later."
        else:
            reply = "Something went wrong. Please try again."
        return {
            "reply": reply,
            "conversation_id": conversation_id,
            "tools_used": [],
            "data": None,
        }

    async def run_scheduled(
        self,
        agent_config: AgentConfig,
        context: dict | None = None,
    ) -> dict:
        """Run a scheduled agent (HEARTBEAT execution).

        Unlike interactive runs, scheduled agents don't have a user message.
        They execute their workflow autonomously based on their system prompt.
        """
        auto_message = (
            f"[SCHEDULED RUN at {datetime.now().isoformat()}] "
            f"Execute your scheduled workflow. "
            f"Context: {json.dumps(context or {})}"
        )

        return await self.run(
            agent_config=agent_config,
            user_message=auto_message,
            user_id="system",
            context=context,
        )
