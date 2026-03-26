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

    # ── Optional: Agent Management (OpenClaw-style) ────────────
    # Override these to enable user-created agents with custom tools,
    # prompts, and scheduled triggers.

    async def save_agent(self, user_id: str, agent_data: dict) -> str:
        """Save or update an agent configuration.

        Args:
            user_id: Owner of the agent
            agent_data: Serialized AgentConfig dict

        Returns:
            The agent ID (generated if new)
        """
        raise NotImplementedError

    async def get_agent(self, agent_id: str) -> dict | None:
        """Get a single agent configuration by ID."""
        raise NotImplementedError

    async def list_agents(self, user_id: str) -> list[dict]:
        """List all agents owned by a user."""
        raise NotImplementedError

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent configuration. Returns True if deleted."""
        raise NotImplementedError

    # ── Optional: Agent Memory Persistence ─────────────────────

    async def save_agent_memory(
        self,
        agent_id: str,
        key: str,
        value: str,
        category: str = "general",
        source: str = "agent",
        timestamp: str = "",
    ) -> None:
        """Save or update a memory entry for an agent."""
        raise NotImplementedError

    async def load_agent_memories(
        self, agent_id: str, category: str | None = None
    ) -> list[dict]:
        """Load all memories for an agent, optionally filtered by category.

        Returns list of dicts with: key, value, category, source, timestamp.
        """
        raise NotImplementedError

    async def delete_agent_memory(self, agent_id: str, key: str) -> None:
        """Delete a specific memory entry."""
        raise NotImplementedError

    async def clear_agent_memories(self, agent_id: str) -> None:
        """Clear all memories for an agent."""
        raise NotImplementedError

    # ── Brain Box Memory (per-feature, per-user) ───────────────

    async def save_brain_memory(
        self,
        namespace: str,
        key: str,
        value: str,
        category: str = "fact",
        metadata: dict | None = None,
    ) -> None:
        """Save a brain box memory entry.

        Args:
            namespace: Brain box namespace (e.g., "brain_todos_user123")
            key: Memory key
            value: Memory value
            category: Category: user, preference, fact, context, history
            metadata: Additional metadata (relevance_score, timestamps, etc.)
        """
        raise NotImplementedError

    async def load_brain_memories(
        self,
        namespace: str,
        category: str | None = None,
    ) -> list[dict]:
        """Load all memories from a brain box namespace.

        Returns list of dicts: {key, value, category, metadata}
        """
        raise NotImplementedError

    async def delete_brain_memory(self, namespace: str, key: str) -> None:
        """Delete a specific brain box memory entry."""
        raise NotImplementedError

    async def clear_brain_namespace(self, namespace: str) -> None:
        """Clear all memories in a brain box namespace."""
        raise NotImplementedError

    # ── Dataset Persistence ────────────────────────────────────

    async def save_dataset_metadata(self, user_id: str, dataset: dict) -> str:
        """Save dataset metadata. Returns dataset ID."""
        raise NotImplementedError

    async def list_datasets(self, user_id: str) -> list[dict]:
        """List all datasets owned by a user."""
        raise NotImplementedError

    async def get_dataset(self, dataset_id: str) -> dict | None:
        """Get dataset metadata by ID."""
        raise NotImplementedError

    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset. Returns True if deleted."""
        raise NotImplementedError

    # ── Todo Persistence ───────────────────────────────────────

    async def save_todo(self, user_id: str, todo: dict) -> str:
        """Save a todo item. Returns todo ID."""
        raise NotImplementedError

    async def list_todos(
        self, user_id: str, status: str | None = None
    ) -> list[dict]:
        """List todos for a user, optionally filtered by status."""
        raise NotImplementedError

    async def update_todo(self, todo_id: str, updates: dict) -> bool:
        """Update a todo item. Returns True if updated."""
        raise NotImplementedError

    async def delete_todo(self, todo_id: str) -> bool:
        """Delete a todo. Returns True if deleted."""
        raise NotImplementedError

    # ── Notes Persistence ──────────────────────────────────────

    async def save_note(self, user_id: str, note: dict) -> str:
        """Save a note. Returns note ID."""
        raise NotImplementedError

    async def list_notes(self, user_id: str, limit: int = 20) -> list[dict]:
        """List notes for a user."""
        raise NotImplementedError

    async def get_note(self, note_id: str) -> dict | None:
        """Get a note by ID."""
        raise NotImplementedError

    async def delete_note(self, note_id: str) -> bool:
        """Delete a note. Returns True if deleted."""
        raise NotImplementedError

    # ── Events Persistence ─────────────────────────────────────

    async def save_event(self, user_id: str, event: dict) -> str:
        """Save an event. Returns event ID."""
        raise NotImplementedError

    async def list_events(
        self,
        user_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """List events for a user within an optional date range."""
        raise NotImplementedError

    async def update_event(self, event_id: str, updates: dict) -> bool:
        """Update an event. Returns True if updated."""
        raise NotImplementedError

    async def delete_event(self, event_id: str) -> bool:
        """Delete an event. Returns True if deleted."""
        raise NotImplementedError

    # ── Emergency Persistence ──────────────────────────────────

    async def save_emergency(self, emergency: dict) -> str:
        """Save an emergency record. Returns emergency ID."""
        raise NotImplementedError

    async def list_emergencies(
        self, filters: dict | None = None
    ) -> list[dict]:
        """List emergencies with optional filters."""
        raise NotImplementedError

    async def update_emergency(
        self, emergency_id: str, updates: dict
    ) -> bool:
        """Update an emergency record. Returns True if updated."""
        raise NotImplementedError

    # ── Vehicle Persistence ────────────────────────────────────

    async def save_vehicle(self, user_id: str, vehicle: dict) -> str:
        """Save a vehicle record. Returns vehicle ID."""
        raise NotImplementedError

    async def list_vehicles(self, user_id: str) -> list[dict]:
        """List all vehicles for a user."""
        raise NotImplementedError

    async def save_vehicle_position(
        self, vehicle_id: str, position: dict
    ) -> None:
        """Save a GPS position record for a vehicle."""
        raise NotImplementedError

    async def get_vehicle_history(
        self, vehicle_id: str, start: str, end: str
    ) -> list[dict]:
        """Get GPS position history for a vehicle."""
        raise NotImplementedError

    # ── Alert Persistence (unified across features) ────────────

    async def save_alert(self, user_id: str, alert: dict) -> str:
        """Save a unified alert. Returns alert ID."""
        raise NotImplementedError

    async def list_alerts(
        self,
        user_id: str,
        alert_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List alerts for a user, optionally filtered by type."""
        raise NotImplementedError

    # ── User Feature Preferences ───────────────────────────────

    async def save_user_preferences(
        self, user_id: str, feature: str, preferences: dict
    ) -> None:
        """Save per-feature preferences for a user."""
        raise NotImplementedError

    async def get_user_preferences(
        self, user_id: str, feature: str | None = None
    ) -> dict:
        """Get user preferences, optionally for a specific feature."""
        raise NotImplementedError
