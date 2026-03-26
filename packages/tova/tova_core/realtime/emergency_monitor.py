"""
Emergency escalation monitor.

Background task that checks for unacknowledged emergencies
and auto-escalates based on severity and time thresholds.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from tova_core.providers.store import BaseStore
from tova_core.providers.notifier import BaseNotifier
from tova_core.providers.telephony import BaseTelephony

logger = logging.getLogger(__name__)

# Escalation thresholds (seconds since creation without acknowledgement)
ESCALATION_THRESHOLDS = {
    "critical": [60, 180, 300],     # 1min -> 3min -> 5min
    "high": [300, 600, 1800],       # 5min -> 10min -> 30min
    "medium": [1800, 3600, 7200],   # 30min -> 1hr -> 2hr
    "low": [7200, 14400, 28800],    # 2hr -> 4hr -> 8hr
}


class EmergencyMonitor:
    """Background monitor that auto-escalates emergencies.

    Runs on a configurable interval, checking for emergencies that
    need attention. Escalation actions:
    - Level 1: Push notification to assigned responders
    - Level 2: SMS to assigned responders + admin
    - Level 3: Phone call to admin/emergency contacts
    """

    def __init__(
        self,
        store: BaseStore,
        notifier: BaseNotifier | None = None,
        telephony: BaseTelephony | None = None,
        check_interval: int = 30,
    ):
        self.store = store
        self.notifier = notifier
        self.telephony = telephony
        self.check_interval = check_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the emergency monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Emergency monitor started (interval: {self.check_interval}s)")

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Emergency monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_escalations()
            except Exception as e:
                logger.error(f"Emergency monitor error: {e}")
            await asyncio.sleep(self.check_interval)

    async def _check_escalations(self) -> None:
        """Check all active emergencies for escalation needs."""
        try:
            emergencies = await self.store.list_emergencies(
                filters={"status__in": ["reported", "acknowledged", "escalated"]}
            )
        except NotImplementedError:
            return
        except Exception as e:
            logger.warning(f"Failed to list emergencies: {e}")
            return

        now = datetime.now()
        for emergency in emergencies:
            await self._evaluate_escalation(emergency, now)

    async def _evaluate_escalation(
        self, emergency: dict[str, Any], now: datetime
    ) -> None:
        """Evaluate if an emergency needs escalation."""
        severity = emergency.get("severity", "medium")
        current_level = emergency.get("escalation_level", 0)
        created_at_str = emergency.get("created_at", "")

        if not created_at_str:
            return

        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            return

        elapsed = (now - created_at).total_seconds()
        thresholds = ESCALATION_THRESHOLDS.get(severity, ESCALATION_THRESHOLDS["medium"])

        # Check if we should escalate to the next level
        if current_level < len(thresholds) and elapsed >= thresholds[current_level]:
            new_level = current_level + 1
            await self._escalate(emergency, new_level)

    async def _escalate(self, emergency: dict[str, Any], level: int) -> None:
        """Execute escalation actions for the given level."""
        emergency_id = emergency.get("id", "unknown")
        severity = emergency.get("severity", "unknown")
        description = emergency.get("description", "Emergency reported")
        contact_numbers = emergency.get("contact_numbers", [])

        logger.warning(
            f"Escalating emergency {emergency_id} to level {level} "
            f"(severity: {severity})"
        )

        # Update emergency record
        try:
            await self.store.update_emergency(
                emergency_id,
                {
                    "escalation_level": level,
                    "status": "escalated",
                    "updated_at": datetime.now().isoformat(),
                },
            )
        except (NotImplementedError, Exception) as e:
            logger.warning(f"Failed to update emergency {emergency_id}: {e}")

        # Level 1: Push notification
        if level >= 1 and self.notifier:
            try:
                reporter_id = emergency.get("reporter_id", "")
                if reporter_id:
                    await self.notifier.notify(
                        user_id=reporter_id,
                        title=f"Emergency Alert - {severity.upper()}",
                        body=description[:200],
                        data={"emergency_id": emergency_id, "level": level},
                    )
            except Exception as e:
                logger.warning(f"Failed to send push notification: {e}")

        # Level 2: SMS
        if level >= 2 and self.telephony and contact_numbers:
            for number in contact_numbers[:5]:  # Limit to 5 numbers
                try:
                    await self.telephony.send_sms(
                        to_number=number,
                        message=f"EMERGENCY ({severity}): {description[:140]}",
                    )
                except (NotImplementedError, Exception) as e:
                    logger.warning(f"Failed to send SMS to {number}: {e}")

        # Level 3: Phone call
        if level >= 3 and self.telephony and contact_numbers:
            primary_number = contact_numbers[0]
            try:
                await self.telephony.make_call(
                    to_number=primary_number,
                    message=(
                        f"This is an automated emergency alert. "
                        f"Severity: {severity}. {description}. "
                        f"Please respond immediately."
                    ),
                    priority="critical",
                )
            except (NotImplementedError, Exception) as e:
                logger.warning(f"Failed to make emergency call to {primary_number}: {e}")
