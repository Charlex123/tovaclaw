"""
Agent Scheduler — HEARTBEAT.md equivalent.

Runs agents on cron schedules or in response to events.
Integrates with the AgentRuntime to execute scheduled agent turns.

Usage:
    scheduler = AgentScheduler(runtime=runtime, store=store)

    # Register agents with scheduled triggers
    scheduler.register(agent_config)

    # Start the scheduler loop
    await scheduler.start()

    # Or trigger an event manually
    await scheduler.trigger_event("prospect_discovered", {"prospect_id": "..."})
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from tova_core.models.agent import AgentConfig, TriggerType
from tova_core.agents.runtime import AgentRuntime

logger = logging.getLogger(__name__)


def _cron_matches_now(cron_expr: str, now: datetime | None = None) -> bool:
    """Simple cron matcher supporting: minute hour day_of_month month day_of_week.

    Supports: exact numbers, * (any), */N (every N).
    Examples:
        "0 9 * * *"     → 9:00 AM every day
        "*/30 * * * *"  → every 30 minutes
        "0 */2 * * *"   → every 2 hours
        "0 9 * * 1"     → 9:00 AM every Monday
    """
    if now is None:
        now = datetime.now()

    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False

    fields = [
        (parts[0], now.minute),
        (parts[1], now.hour),
        (parts[2], now.day),
        (parts[3], now.month),
        (parts[4], now.weekday()),  # 0=Monday in Python
    ]

    for pattern, current in fields:
        if pattern == "*":
            continue
        if pattern.startswith("*/"):
            divisor = int(pattern[2:])
            if current % divisor != 0:
                return False
        else:
            if int(pattern) != current:
                return False

    return True


class AgentScheduler:
    """Runs agents on schedules and in response to events.

    The scheduler maintains a registry of agents with their trigger configs.
    It checks every minute which agents should run and executes them.
    """

    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime
        self._agents: dict[str, AgentConfig] = {}
        self._event_handlers: dict[str, list[str]] = {}  # event_name → [agent_ids]
        self._run_counts: dict[str, int] = {}  # agent_id → runs today
        self._last_reset_date: str = ""
        self._running = False

    def register(self, agent: AgentConfig) -> None:
        """Register an agent for scheduled or event-based execution."""
        self._agents[agent.id] = agent

        if agent.trigger.type == TriggerType.EVENT and agent.trigger.event:
            event = agent.trigger.event
            if event not in self._event_handlers:
                self._event_handlers[event] = []
            if agent.id not in self._event_handlers[event]:
                self._event_handlers[event].append(agent.id)

        logger.info(f"Scheduler: registered '{agent.name}' ({agent.trigger.type.value})")

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the scheduler."""
        agent = self._agents.pop(agent_id, None)
        if agent and agent.trigger.event:
            handlers = self._event_handlers.get(agent.trigger.event, [])
            if agent_id in handlers:
                handlers.remove(agent_id)

    async def start(self, check_interval: int = 60) -> None:
        """Start the scheduler loop. Checks every `check_interval` seconds."""
        self._running = True
        logger.info(f"Scheduler started (checking every {check_interval}s)")

        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}")

            await asyncio.sleep(check_interval)

    def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        logger.info("Scheduler stopped")

    async def _tick(self) -> None:
        """Check all scheduled agents and run those whose cron matches now."""
        now = datetime.now()

        # Reset daily run counts
        today = now.strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._run_counts.clear()
            self._last_reset_date = today

        for agent_id, agent in self._agents.items():
            if agent.trigger.type != TriggerType.SCHEDULED:
                continue
            if not agent.trigger.cron:
                continue
            if agent.status.value != "active":
                continue

            # Check daily limit
            if agent.trigger.max_runs_per_day:
                runs = self._run_counts.get(agent_id, 0)
                if runs >= agent.trigger.max_runs_per_day:
                    continue

            if _cron_matches_now(agent.trigger.cron, now):
                logger.info(f"Scheduler: running '{agent.name}' (cron: {agent.trigger.cron})")
                try:
                    result = await self.runtime.run_scheduled(
                        agent_config=agent,
                        context={"triggered_by": "scheduler", "scheduled_time": now.isoformat()},
                    )
                    self._run_counts[agent_id] = self._run_counts.get(agent_id, 0) + 1
                    logger.info(
                        f"Scheduler: '{agent.name}' completed. "
                        f"Tools: {result.get('tools_used', [])}"
                    )
                except Exception as e:
                    logger.error(f"Scheduler: '{agent.name}' failed: {e}")

    async def trigger_event(self, event_name: str, data: dict[str, Any] | None = None) -> list[dict]:
        """Trigger all agents listening for this event.

        Args:
            event_name: The event identifier (e.g., "prospect_discovered")
            data: Event payload passed as context to the agent

        Returns:
            List of results from each triggered agent
        """
        agent_ids = self._event_handlers.get(event_name, [])
        if not agent_ids:
            logger.debug(f"No agents registered for event '{event_name}'")
            return []

        results = []
        for agent_id in agent_ids:
            agent = self._agents.get(agent_id)
            if not agent or agent.status.value != "active":
                continue

            logger.info(f"Event '{event_name}' → running '{agent.name}'")
            try:
                context = {
                    "triggered_by": "event",
                    "event_name": event_name,
                    **(data or {}),
                }
                result = await self.runtime.run_scheduled(
                    agent_config=agent,
                    context=context,
                )
                results.append({"agent_id": agent_id, "agent_name": agent.name, **result})
            except Exception as e:
                logger.error(f"Event handler '{agent.name}' failed: {e}")
                results.append({"agent_id": agent_id, "agent_name": agent.name, "error": str(e)})

        return results

    def list_scheduled(self) -> list[dict[str, Any]]:
        """List all registered agents with their trigger info."""
        return [
            {
                "agent_id": agent.id,
                "name": agent.name,
                "trigger_type": agent.trigger.type.value,
                "cron": agent.trigger.cron,
                "event": agent.trigger.event,
                "status": agent.status.value,
                "runs_today": self._run_counts.get(agent.id, 0),
                "max_runs_per_day": agent.trigger.max_runs_per_day,
            }
            for agent in self._agents.values()
        ]
