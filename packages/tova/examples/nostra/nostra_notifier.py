"""Nostra Health notifier — FCM push notifications."""

import logging
from tova_core.providers.notifier import BaseNotifier

logger = logging.getLogger(__name__)


class NostraNotifier(BaseNotifier):
    """Sends push notifications via Firebase Cloud Messaging."""

    async def notify(self, user_id, title, body, icon="notification", data=None):
        try:
            import firebase_admin
            from firebase_admin import messaging
            from google.cloud.firestore_v1 import AsyncClient, SERVER_TIMESTAMP

            # Get FCM token
            # (In production, cache this or use a shared Firestore client)
            import os
            project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
            db = AsyncClient(project=project_id)
            doc = await db.collection("users").document(user_id).get()
            if not doc.exists:
                return

            fcm_token = doc.to_dict().get("fcmToken")
            if not fcm_token:
                return

            # Send push notification
            string_data = {k: str(v) for k, v in (data or {}).items()}
            message = messaging.Message(
                token=fcm_token,
                notification=messaging.Notification(title=title, body=body),
                data=string_data,
            )
            messaging.send(message)

            # Save in-app notification
            await db.collection("notifications").add({
                "userId": user_id,
                "title": title,
                "message": body,
                "icon": icon,
                "status": "unread",
                "data": data or {},
                "createdAt": SERVER_TIMESTAMP,
            })
        except Exception as e:
            logger.warning(f"Notification failed for {user_id}: {e}")
