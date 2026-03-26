"""
Standalone notification provider — works without Firebase.

Two modes:
1. SQLite-backed in-app notifications (always works, no setup)
2. Optional webhook delivery (POST to any URL — Slack, Discord, custom)

For push notifications to mobile apps, use Firebase (NostraNotifier)
or implement your own BaseNotifier with OneSignal, Pusher, etc.

Usage:
    # In-app only (zero config):
    notifier = StandaloneNotifier(store=my_store)

    # With webhook (Slack, Discord, custom endpoint):
    notifier = StandaloneNotifier(
        store=my_store,
        webhook_url="https://hooks.slack.com/services/T.../B.../xxx",
    )

    # From env vars:
    TOVA_WEBHOOK_URL=https://hooks.slack.com/...
    notifier = StandaloneNotifier(store=my_store)

    # Send notification:
    await notifier.notify("user123", "Alert", "Your todo is due")
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from tova_core.providers.notifier import BaseNotifier
from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


class StandaloneNotifier(BaseNotifier):
    """Standalone notification provider.

    Stores all notifications in the database (queryable via /alerts).
    Optionally forwards to a webhook URL for real-time delivery.
    """

    def __init__(
        self,
        store: BaseStore | None = None,
        webhook_url: str | None = None,
        webhook_headers: dict | None = None,
    ):
        self.store = store
        self.webhook_url = webhook_url or os.environ.get("TOVA_WEBHOOK_URL", "")
        self.webhook_headers = webhook_headers or {}

    async def notify(
        self,
        user_id: str,
        title: str,
        body: str,
        icon: str = "notification",
        data: dict | None = None,
    ) -> None:
        """Send a notification — stores in DB + optional webhook."""
        now = datetime.now(timezone.utc).isoformat()

        notification = {
            "type": "notification",
            "source": "tova",
            "severity": data.get("severity", "info") if data else "info",
            "message": f"{title}: {body}",
            "data": {
                "title": title,
                "body": body,
                "icon": icon,
                **(data or {}),
                "timestamp": now,
            },
        }

        # Store in database (always)
        if self.store:
            try:
                await self.store.save_alert(user_id=user_id, alert=notification)
            except (NotImplementedError, Exception) as e:
                logger.debug(f"Could not persist notification: {e}")

        # Forward to webhook (if configured)
        if self.webhook_url:
            await self._send_webhook(user_id, title, body, data)

        logger.info(f"Notification: [{title}] {body[:80]} → user {user_id[:16]}...")

    async def _send_webhook(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> None:
        """POST notification to webhook URL."""
        try:
            import httpx

            payload: dict[str, Any]

            # Detect Slack webhook format
            if "hooks.slack.com" in self.webhook_url:
                payload = {
                    "text": f"*{title}*\n{body}",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*{title}*\n{body}",
                            },
                        },
                    ],
                }
            # Detect Discord webhook format
            elif "discord.com/api/webhooks" in self.webhook_url:
                payload = {
                    "content": f"**{title}**\n{body}",
                    "embeds": [
                        {
                            "title": title,
                            "description": body,
                            "color": 0xFF4444 if data and data.get("severity") == "critical" else 0x4488FF,
                        }
                    ],
                }
            else:
                # Generic webhook
                payload = {
                    "user_id": user_id,
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            headers = {"Content-Type": "application/json", **self.webhook_headers}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers=headers,
                )
                if response.status_code >= 400:
                    logger.warning(
                        f"Webhook delivery failed ({response.status_code}): "
                        f"{response.text[:200]}"
                    )

        except Exception as e:
            logger.warning(f"Webhook delivery error: {e}")

    async def call(
        self,
        to_number: str,
        message: str,
        priority: str = "normal",
    ) -> dict:
        """Phone call via webhook fallback (not a real call).

        For real phone calls, use TwilioTelephony.
        This just posts to the webhook for human follow-up.
        """
        if self.webhook_url:
            await self._send_webhook(
                user_id="__system__",
                title=f"📞 CALL REQUESTED ({priority.upper()})",
                body=f"To: {to_number}\nMessage: {message}",
                data={"severity": priority, "type": "call_request"},
            )

        return {
            "call_id": f"webhook_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "status": "webhook_sent" if self.webhook_url else "not_configured",
            "note": "Notification sent via webhook. For real calls, configure TwilioTelephony.",
        }

    async def sms(
        self,
        to_number: str,
        message: str,
    ) -> dict:
        """SMS via webhook fallback (not a real SMS).

        For real SMS, use TwilioTelephony.
        """
        if self.webhook_url:
            await self._send_webhook(
                user_id="__system__",
                title=f"💬 SMS REQUESTED",
                body=f"To: {to_number}\nMessage: {message}",
                data={"type": "sms_request"},
            )

        return {
            "message_id": f"webhook_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "status": "webhook_sent" if self.webhook_url else "not_configured",
        }
