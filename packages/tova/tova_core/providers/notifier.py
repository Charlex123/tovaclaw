"""
Abstract notification interface.

Implement this class to send push notifications and in-app alerts.
"""

from abc import ABC


class BaseNotifier(ABC):
    """Notification provider — sends push notifications and in-app alerts.

    This is optional. If not provided, Tova will skip notifications silently.
    Implement with your own notification system (FCM, OneSignal, SNS, etc.).
    """

    async def notify(
        self,
        user_id: str,
        title: str,
        body: str,
        icon: str = "notification",
        data: dict | None = None,
    ) -> None:
        """Send a notification to a user.

        Args:
            user_id: The user to notify
            title: Notification title
            body: Notification body text
            icon: Icon identifier
            data: Optional structured data payload
        """
        pass  # Default: do nothing (notifications are optional)

    async def call(
        self,
        to_number: str,
        message: str,
        priority: str = "normal",
    ) -> dict:
        """Make a phone call notification. Optional — override if supported.

        Args:
            to_number: Phone number in E.164 format
            message: Message to speak via TTS
            priority: normal, high, critical

        Returns:
            {"call_id": str, "status": str}
        """
        raise NotImplementedError("Call notifications not configured")

    async def sms(
        self,
        to_number: str,
        message: str,
    ) -> dict:
        """Send an SMS notification. Optional — override if supported.

        Args:
            to_number: Phone number in E.164 format
            message: SMS text

        Returns:
            {"message_id": str, "status": str}
        """
        raise NotImplementedError("SMS notifications not configured")
