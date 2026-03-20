"""
Minimal Tova example — in-memory e-commerce providers for quick testing.

Run with:
    pip install "tova[anthropic]"
    export ANTHROPIC_API_KEY=sk-ant-...
    uvicorn main:app --port 8000

Then:
    curl -X POST http://localhost:8000/agent/chat \
      -H "Authorization: Bearer test-user-123" \
      -H "Content-Type: application/json" \
      -d '{"message": "Find me a laptop under $1000"}'
"""

import uuid
from datetime import datetime
from tova_core.app import create_app
from tova_core.providers.backend import BaseBackend
from tova_core.providers.store import BaseStore
from tova_core.providers.auth import BaseAuth


# ── In-Memory Backend ─────────────────────────────────────────


class InMemoryBackend(BaseBackend):
    """Simple in-memory backend with sample e-commerce product data."""

    PRODUCTS = [
        {"id": "prod-001", "name": "MacBook Air M3", "price": 1099.00, "in_stock": True, "store_name": "TechStore", "category": "laptops", "latitude": 40.71, "longitude": -74.01},
        {"id": "prod-002", "name": "Sony WH-1000XM5 Headphones", "price": 348.00, "in_stock": True, "store_name": "AudioWorld", "category": "audio", "latitude": 40.72, "longitude": -73.99},
        {"id": "prod-003", "name": "Samsung Galaxy S24", "price": 799.99, "in_stock": True, "store_name": "PhoneHub", "category": "phones", "latitude": 40.73, "longitude": -74.00},
        {"id": "prod-004", "name": "Logitech MX Master 3S Mouse", "price": 99.99, "in_stock": True, "store_name": "TechStore", "category": "accessories", "latitude": 40.71, "longitude": -74.01},
        {"id": "prod-005", "name": "iPad Pro 13-inch", "price": 1299.00, "in_stock": True, "store_name": "TechStore", "category": "tablets", "latitude": 40.71, "longitude": -74.01},
    ]

    SERVICES = [
        {"id": "svc-001", "name": "Screen Repair", "price": 149.00, "provider_name": "FixIt Pro", "category": "repair"},
        {"id": "svc-002", "name": "Data Recovery", "price": 199.00, "provider_name": "DataSafe", "category": "repair"},
        {"id": "svc-003", "name": "Device Setup & Transfer", "price": 79.00, "provider_name": "TechStore", "category": "setup"},
    ]

    _orders = {}

    async def search_products(self, query, latitude=0, longitude=0, **kwargs):
        q = query.lower()
        return [p for p in self.PRODUCTS if q in p["name"].lower() or q in p.get("category", "").lower()]

    async def search_services(self, query, latitude=0, longitude=0, **kwargs):
        q = query.lower()
        return [s for s in self.SERVICES if q in s["name"].lower() or q in s.get("category", "").lower()]

    async def create_order(self, data):
        order_id = f"ord-{uuid.uuid4().hex[:8]}"
        self._orders[order_id] = {**data, "id": order_id, "status": "pending"}
        return {"id": order_id, "success": True}

    async def execute_order(self, order_id):
        if order_id in self._orders:
            self._orders[order_id]["status"] = "completed"
            return {"success": True, "message": "Order executed"}
        return {"success": False, "message": "Order not found"}

    async def cancel_order(self, order_id, reason=""):
        if order_id in self._orders:
            self._orders[order_id]["status"] = "cancelled"
            return {"success": True, "message": "Order cancelled"}
        return {"success": False, "message": "Order not found"}

    async def check_balance(self, user_id):
        return {"balance": 2000.00, "currency": "USD"}

    async def process_payment(self, data):
        return {"success": True, "transaction_id": f"txn-{uuid.uuid4().hex[:8]}"}


# ── In-Memory Store ───────────────────────────────────────────


class InMemoryStore(BaseStore):
    """Simple in-memory store for testing."""

    _users = {
        "test-user-123": {
            "id": "test-user-123",
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+1234567890",
            "address": "123 Main Street, New York, NY",
        }
    }
    _conversations: dict[str, dict] = {}
    _orders: dict[str, dict] = {}

    async def get_user(self, user_id):
        return self._users.get(user_id)

    async def get_balance(self, user_id):
        return {"balance": 2000.00, "currency": "USD"}

    async def get_orders(self, user_id, status=None, order_type=None, limit=10):
        return [o for o in self._orders.values() if o.get("user_id") == user_id][:limit]

    async def get_order(self, order_id):
        return self._orders.get(order_id)

    async def save_conversation(self, conversation_id, user_id, messages, title=""):
        if conversation_id in self._conversations:
            self._conversations[conversation_id]["messages"].extend(messages)
        else:
            self._conversations[conversation_id] = {
                "user_id": user_id,
                "title": title,
                "messages": messages,
                "created_at": datetime.now().isoformat(),
            }

    async def load_conversation(self, conversation_id):
        conv = self._conversations.get(conversation_id)
        return conv["messages"] if conv else []

    async def list_conversations(self, user_id, limit=20):
        return [
            {"id": cid, "title": c.get("title", "Chat"), "message_count": len(c.get("messages", []))}
            for cid, c in self._conversations.items()
            if c.get("user_id") == user_id
        ][:limit]

    async def generate_id(self):
        return uuid.uuid4().hex


# ── Simple Auth ───────────────────────────────────────────────


class SimpleAuth(BaseAuth):
    """Auth that uses the token directly as the user ID (for testing only)."""

    async def verify_token(self, token: str) -> str:
        return token  # Token IS the user ID


# ── Create App ────────────────────────────────────────────────

app = create_app(
    backend_factory=lambda token: InMemoryBackend(auth_token=token),
    store=InMemoryStore(),
    auth=SimpleAuth(),
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
