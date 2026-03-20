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
