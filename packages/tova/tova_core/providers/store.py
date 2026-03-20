"""
Abstract data store interface.

Implement this class to connect Tova to your database.
All read operations (user profiles, order history, conversations) go through this.
"""

from abc import ABC, abstractmethod


class BaseStore(ABC):
    """Data store provider — handles all read operations and conversation persistence.

    This replaces direct Firestore access. Implement with your own database
    (PostgreSQL, MongoDB, MySQL, DynamoDB, etc.).
    """

    # ── Required: User Data ───────────────────────────────────

    @abstractmethod
    async def get_user(self, user_id: str) -> dict | None:
        """Get user profile.

        Returns dict with at minimum:
            - id: User ID
            - name: Full name
            - email: Email (optional)
            - phone: Phone number (optional)
            - address: Default address (optional)
        """
        ...

    @abstractmethod
    async def get_balance(self, user_id: str) -> dict:
        """Get user's wallet/payment balance.

        Returns: {"balance": float, "currency": "USD"}
        """
        ...

    # ── Required: Order Data ──────────────────────────────────

    @abstractmethod
    async def get_orders(
        self,
        user_id: str,
        status: str | None = None,
        order_type: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get user's order history.

        Returns list of order dicts with: id, status, item_name, scheduled_date, cost, etc.
        """
        ...

    @abstractmethod
    async def get_order(self, order_id: str) -> dict | None:
        """Get a single order by ID."""
        ...

    # ── Required: Conversation Persistence ────────────────────

    @abstractmethod
    async def save_conversation(
        self,
        conversation_id: str,
        user_id: str,
        messages: list[dict],
        title: str = "",
    ) -> None:
        """Save or append conversation messages.

        Args:
            conversation_id: Unique conversation ID
            user_id: User who owns this conversation
            messages: List of message dicts [{role, content, timestamp, ...}]
            title: Conversation title (usually first user message)
        """
        ...

    @abstractmethod
    async def load_conversation(self, conversation_id: str) -> list[dict]:
        """Load conversation messages by ID.

        Returns list of message dicts.
        """
        ...

    @abstractmethod
    async def list_conversations(self, user_id: str, limit: int = 20) -> list[dict]:
        """List user's conversations (metadata only, not full messages).

        Returns list of dicts with: id, title, message_count, updated_at, created_at.
        """
        ...

    @abstractmethod
    async def generate_id(self) -> str:
        """Generate a unique ID for a new conversation."""
        ...

    # ── Optional: Product/Service Search (read-only) ──────────
    # These provide a fast read path (e.g., direct DB query) as an
    # alternative to going through the backend API. If not implemented,
    # the tools will use BaseBackend.search_products() instead.

    async def search_products(self, query: str, limit: int = 10) -> list[dict]:
        """Search products directly from the database (fast path).

        Override this if you want to bypass the backend API for searches.
        Returns same format as BaseBackend.search_products().
        """
        raise NotImplementedError

    async def search_services(self, query: str, limit: int = 10) -> list[dict]:
        """Search services directly from the database (fast path)."""
        raise NotImplementedError

    # ── Optional: Practitioner/Appointment Data ───────────────

    async def search_practitioners(
        self,
        practitioner_type: str = "doctor",
        specialty: str = "",
        query: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """Search practitioners directly from the database."""
        raise NotImplementedError

    async def get_appointments(
        self,
        user_id: str,
        appointment_type: str = "",
        status: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """Get user's appointment history."""
        raise NotImplementedError

    async def get_practitioner_specialties(self) -> list[str]:
        """Get all available practitioner specialties."""
        raise NotImplementedError

    # ── Optional: Safety Data ─────────────────────────────────

    async def check_drug_safety(self, drug_name: str) -> dict:
        """Check drug safety alerts from your database.

        Returns: {"safe": True/False, "warnings": [...]}
        """
        return {"safe": True, "warnings": [], "message": f"No safety data available for {drug_name}"}

    # ── Optional: Pending Conversations ───────────────────────

    async def get_pending_conversation(self, user_id: str) -> dict | None:
        """Find conversations with unfulfilled requests.

        Returns dict with: conversation_id, title, last_action, last_message.
        Or None if no pending conversations.
        """
        return None
