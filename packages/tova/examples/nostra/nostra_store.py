"""
Nostra Health data store — reads from Firestore.

This implements BaseStore using Google Cloud Firestore for all read operations.
"""

import os
import json
import uuid
import logging

from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


class NostraFirestoreStore(BaseStore):
    """Nostra's Firestore-backed data store."""

    def __init__(self):
        self._db = None

    async def _get_db(self):
        if self._db is None:
            from google.cloud.firestore_v1 import AsyncClient
            sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
            project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
            if sa_json:
                from google.oauth2 import service_account as sa
                creds = sa.Credentials.from_service_account_info(json.loads(sa_json))
                self._db = AsyncClient(project=project_id, credentials=creds)
            else:
                self._db = AsyncClient(project=project_id)
        return self._db

    async def get_user(self, user_id):
        db = await self._get_db()
        doc = await db.collection("users").document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            data["name"] = data.get("fullName", data.get("firstName", ""))
            data["phone"] = data.get("phoneNumber", "")
            return data
        return None

    async def get_balance(self, user_id):
        db = await self._get_db()
        doc = await db.collection("patients_wallets").document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            balance = data.get("balance_naira", 0)
            return {"balance": float(balance) if isinstance(balance, str) else balance, "currency": "NGN"}
        # Fallback
        doc = await db.collection("wallets").document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            balance = data.get("paystack_account_balance", 0)
            return {"balance": float(balance) if isinstance(balance, str) else balance, "currency": "NGN"}
        return {"balance": 0, "currency": "NGN"}

    async def get_orders(self, user_id, status=None, order_type=None, limit=10):
        db = await self._get_db()
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = db.collection("automated_requests").where(filter=FieldFilter("userId", "==", user_id))
        if status:
            query = query.where(filter=FieldFilter("status", "==", status))
        if order_type:
            query = query.where(filter=FieldFilter("requestType", "==", order_type))
        query = query.order_by("createdAt", direction="DESCENDING").limit(limit)

        results = []
        async for doc in query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            # Normalize to generic field names
            rd = data.get("requestData", {})
            data["item_name"] = rd.get("itemName") or rd.get("testName")
            data["item_id"] = rd.get("itemId") or rd.get("testId")
            data["type"] = data.get("requestType")
            data["cost"] = data.get("costPerExecution")
            data["delivery_address"] = data.get("deliveryAddress")
            data["scheduled_date"] = data.get("scheduledDate")
            data["schedule_type"] = data.get("scheduleType")
            data["created_at"] = str(data.get("createdAt", ""))
            results.append(data)
        return results

    async def get_order(self, order_id):
        db = await self._get_db()
        doc = await db.collection("automated_requests").document(order_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            rd = data.get("requestData", {})
            data["user_id"] = data.get("userId")
            data["item_name"] = rd.get("itemName") or rd.get("testName")
            data["item_id"] = rd.get("itemId") or rd.get("testId")
            data["type"] = data.get("requestType")
            data["cost"] = data.get("costPerExecution")
            data["delivery_address"] = data.get("deliveryAddress")
            return data
        return None

    async def save_conversation(self, conversation_id, user_id, messages, title=""):
        db = await self._get_db()
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP
        doc_ref = db.collection("tova_conversations").document(conversation_id)
        existing = await doc_ref.get()

        if existing.exists:
            existing_msgs = existing.to_dict().get("messages", [])
            all_msgs = (existing_msgs + messages)[-40:]
            await doc_ref.update({
                "messages": all_msgs,
                "messageCount": len(all_msgs),
                "updatedAt": SERVER_TIMESTAMP,
            })
        else:
            await doc_ref.set({
                "userId": user_id,
                "title": title,
                "messages": messages,
                "messageCount": len(messages),
                "createdAt": SERVER_TIMESTAMP,
                "updatedAt": SERVER_TIMESTAMP,
            })

    async def load_conversation(self, conversation_id):
        db = await self._get_db()
        doc = await db.collection("tova_conversations").document(conversation_id).get()
        if doc.exists:
            return doc.to_dict().get("messages", [])
        return []

    async def list_conversations(self, user_id, limit=20):
        db = await self._get_db()
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = (
            db.collection("tova_conversations")
            .where(filter=FieldFilter("userId", "==", user_id))
            .order_by("updatedAt", direction="DESCENDING")
            .limit(limit)
        )
        results = []
        try:
            async for doc in query.stream():
                data = doc.to_dict()
                results.append({
                    "id": doc.id,
                    "title": data.get("title", "Chat"),
                    "message_count": data.get("messageCount", 0),
                    "updated_at": data.get("updatedAt").isoformat() if data.get("updatedAt") else None,
                    "created_at": data.get("createdAt").isoformat() if data.get("createdAt") else None,
                })
        except Exception:
            pass
        return results

    async def generate_id(self):
        db = await self._get_db()
        return db.collection("tova_conversations").document().id

    async def check_drug_safety(self, drug_name):
        db = await self._get_db()
        from google.cloud.firestore_v1.base_query import FieldFilter
        result = {"safe": True, "warnings": []}
        try:
            q = db.collection("drug_alerts").where(
                filter=FieldFilter("drug_name_lower", "==", drug_name.lower())
            ).limit(5)
            async for doc in q.stream():
                alert = doc.to_dict()
                if alert.get("severity") == "critical":
                    result["safe"] = False
                result["warnings"].append({
                    "type": alert.get("type", "warning"),
                    "message": alert.get("message", "Safety concern"),
                })
        except Exception:
            pass
        if not result["warnings"]:
            result["message"] = f"No safety concerns for {drug_name}."
        return result

    async def get_appointments(self, user_id, appointment_type="", status="", limit=10):
        db = await self._get_db()
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = db.collection("appointments").where(filter=FieldFilter("userId", "==", user_id))
        if appointment_type:
            query = query.where(filter=FieldFilter("type", "==", appointment_type))
        if status:
            query = query.where(filter=FieldFilter("status", "==", status))
        query = query.limit(limit)

        results = []
        async for doc in query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            data["professional_name"] = data.get("professionalName", "")
            results.append(data)
        return results

    async def get_practitioner_specialties(self):
        db = await self._get_db()
        specialties = []
        async for doc in db.collection("doctor_specialties").stream():
            spec = doc.to_dict().get("specialty")
            if spec:
                specialties.append(spec)
        return sorted(specialties)
