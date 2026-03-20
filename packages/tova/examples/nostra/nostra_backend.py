"""
Nostra Health backend provider — wraps the Node.js backend API.

This implements BaseBackend by making HTTP calls to Nostra's Express API.
"""

import httpx
from tova_core.providers.backend import BaseBackend


class NostraBackend(BaseBackend):
    """Nostra Health backend — proxies to the Node.js API."""

    def __init__(self, auth_token: str | None = None):
        super().__init__(auth_token)
        import os
        base_url = os.environ.get("BACKEND_API_URL", "http://localhost:3000/api/v1")
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30.0)

    async def search_products(self, query, latitude=0, longitude=0, **kwargs):
        resp = await self._client.post("/storeitem/getstoreitemsbysearch", json={
            "searchQuery": query, "latitude": latitude, "longitude": longitude,
        })
        resp.raise_for_status()
        data = resp.json()
        # Flatten Nostra's category-based response
        items = []
        if isinstance(data, dict):
            for category, cat_items in data.items():
                if isinstance(cat_items, list):
                    for item in cat_items:
                        item["category"] = category
                        items.append(item)
        return items

    async def search_services(self, query, latitude=0, longitude=0, **kwargs):
        resp = await self._client.post("/labtest/getlabtestsbysearch", json={
            "searchQuery": query, "latitude": latitude, "longitude": longitude,
        })
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def create_order(self, data):
        # Map generic fields to Nostra's schema
        body = {
            "requestType": data.get("order_type", "medical_items"),
            "scheduleType": data.get("schedule_type", "once"),
            "scheduledDate": data.get("scheduled_date"),
            "deliveryAddress": data.get("delivery_address"),
            "paymentMethod": "wallet",
            "logisticsFee": data.get("delivery_fee", 0),
            "requestData": {
                "itemId": data.get("item_id"),
                "itemName": data.get("item_name"),
                "quantity": data.get("quantity", 1),
            },
            "costPerExecution": data.get("cost"),
            "totalCost": data.get("cost"),
            "isActive": True,
            "source": "tova",
        }
        if data.get("frequency"):
            body["frequency"] = data["frequency"]
            body["duration"] = data.get("duration", "")
        if data.get("is_for_someone_else"):
            body["isForSomeoneElse"] = True
            body["recipientName"] = data.get("recipient_name")
            body["recipientPhone"] = data.get("recipient_phone")

        resp = await self._client.post("/automated-requests", json=body)
        resp.raise_for_status()
        return resp.json()

    async def execute_order(self, order_id):
        resp = await self._client.post(f"/automated-requests/{order_id}/execute")
        resp.raise_for_status()
        return resp.json()

    async def cancel_order(self, order_id, reason=""):
        resp = await self._client.delete(
            f"/automated-requests/{order_id}",
            json={"reason": reason} if reason else None,
        )
        resp.raise_for_status()
        return resp.json()

    async def check_balance(self, user_id):
        # Balance is read from Firestore via the store provider
        # This is a no-op since NostraFirestoreStore handles it
        return {"balance": 0, "currency": "NGN"}

    async def process_payment(self, data):
        resp = await self._client.post("/payment/walletcheckout", json=data)
        resp.raise_for_status()
        return resp.json()

    async def search_practitioners(self, practitioner_type="doctor", specialty="", query="", latitude=0, longitude=0, **kwargs):
        is_doctor = practitioner_type.lower() == "doctor"
        resp = await self._client.post("/schedule/getschedulessearch", json={
            "type": "Doctor" if is_doctor else "Nurse",
            "latitude": latitude,
            "longitude": longitude,
            "searchQuery": query,
            "specialty": specialty,
        })
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def book_appointment(self, data):
        # Create checkout
        checkout_data = {
            "id": data["schedule_id"],
            "scheduleId": data["slot_id"],
            "type": data["appointment_type"],
            "professionalId": data["professional_id"],
            "name": data["professional_name"],
            "amount": data["amount"],
            "specialty": data.get("specialty", ""),
            "source": "tova",
        }
        resp = await self._client.post("/addcheckout", json=checkout_data)
        resp.raise_for_status()
        result = resp.json()
        checkout_id = result.get("id", result.get("checkoutId", ""))

        # Process wallet payment
        await self._client.post("/payment/walletcheckout", json={"amount": data["amount"]})

        # Mark slot as booked
        await self._client.put(
            f"/updatebyschedule/{data['schedule_id']}/{data['slot_id']}",
            json={"status": "booked"},
        )

        return {"appointment_id": checkout_id, "checkout_id": checkout_id}

    async def cancel_appointment(self, appointment_id, reason=""):
        resp = await self._client.put(f"/updateappointment/{appointment_id}", json={
            "status": "cancelled",
            "cancellationReason": reason,
        })
        resp.raise_for_status()
        return resp.json()

    async def calculate_delivery_fee(self, data):
        resp = await self._client.post("/calculate-logistics-fee", json={
            "itemType": data.get("item_type"),
            "storeCenterId": data.get("store_id"),
            "userAddress": data.get("delivery_address"),
        })
        resp.raise_for_status()
        result = resp.json()
        return {"fee": result.get("logisticsFee", 700), "currency": "NGN"}

    async def verify_identity(self, data):
        resp = await self._client.post("/verify-nin", json={
            "userNIN": data.get("id_number"),
            "country": data.get("country", "NG"),
            "id_type": "NIN_V2",
        })
        resp.raise_for_status()
        result = resp.json()
        return {"verified": result.get("isNINVerified", False)}

    async def close(self):
        await self._client.aclose()
