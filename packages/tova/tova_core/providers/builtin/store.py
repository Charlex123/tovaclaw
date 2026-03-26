"""
Built-in SQLite store — full BaseStore implementation with zero external services.

This is the default store for standalone Tova deployments. Everything lives
in a single SQLite database file — conversations, agents, todos, notes,
events, emergencies, vehicles, alerts, user preferences.

Uses aiosqlite for async I/O and WAL journal mode for concurrent reads.

Usage:
    store = SQLiteStore()                           # ~/.tova/tova.db
    store = SQLiteStore(db_path="/data/tova.db")    # custom path
    TOVA_STORE_DB=/data/tova.db                     # via env var
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".tova" / "tova.db"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


_SCHEMA = """
-- Users (lightweight, stores profile data as JSON)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at DESC);

-- Conversation messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tools_used TEXT DEFAULT '[]',
    data TEXT,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, timestamp);

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_user ON agents(user_id);

-- Todos
CREATE TABLE IF NOT EXISTS todos (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_todo_user ON todos(user_id);

-- Notes
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_note_user ON notes(user_id);

-- Events
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_user ON events(user_id);

-- Emergencies
CREATE TABLE IF NOT EXISTS emergencies (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Vehicles
CREATE TABLE IF NOT EXISTS vehicles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vehicle_user ON vehicles(user_id);

-- Vehicle position history
CREATE TABLE IF NOT EXISTS vehicle_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vpos_vehicle ON vehicle_positions(vehicle_id, recorded_at);

-- Alerts (unified)
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    alert_type TEXT DEFAULT '',
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_user ON alerts(user_id, created_at DESC);

-- Datasets
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dataset_user ON datasets(user_id);

-- User preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT NOT NULL,
    feature TEXT NOT NULL,
    preferences TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, feature)
);

-- Brain box memories (for BaseStore brain_memory methods)
CREATE TABLE IF NOT EXISTS brain_memories_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'fact',
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(namespace, key)
);
CREATE INDEX IF NOT EXISTS idx_brain_store_ns ON brain_memories_store(namespace);

-- Agent memories
CREATE TABLE IF NOT EXISTS agent_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    source TEXT DEFAULT 'agent',
    timestamp TEXT NOT NULL,
    UNIQUE(agent_id, key)
);
CREATE INDEX IF NOT EXISTS idx_agentmem_agent ON agent_memories(agent_id);
"""


class SQLiteStore(BaseStore):
    """Full BaseStore implementation backed by local SQLite.

    This is the batteries-included store for standalone Tova deployments.
    Every BaseStore method is implemented — agents, todos, notes, events,
    emergencies, vehicles, alerts, conversations, preferences, brain memory.

    All data lives in a single SQLite file with WAL mode for performance.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get("TOVA_STORE_DB", str(_DEFAULT_DB))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.executescript(_SCHEMA)
            await db.commit()
        self._initialized = True

    async def _conn(self):
        """Get a new connection (caller must use as async context manager)."""
        await self._ensure_init()
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    def _gen_id(self) -> str:
        return str(uuid.uuid4())

    # ── Helper: JSON entity CRUD ──────────────────────────────

    async def _save_entity(
        self, table: str, entity_id: str | None, user_id: str, data: dict
    ) -> str:
        eid = entity_id or data.get("id") or self._gen_id()
        now = _utcnow()
        data["id"] = eid
        if user_id:
            data["user_id"] = user_id

        db = await self._conn()
        try:
            await db.execute(f"""
                INSERT INTO {table} (id, user_id, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
            """, (eid, user_id, json.dumps(data, default=str), now, now))
            await db.commit()
            return eid
        finally:
            await db.close()

    async def _get_entity(self, table: str, entity_id: str) -> dict | None:
        db = await self._conn()
        try:
            cursor = await db.execute(
                f"SELECT data FROM {table} WHERE id = ?", (entity_id,)
            )
            row = await cursor.fetchone()
            return json.loads(row["data"]) if row else None
        finally:
            await db.close()

    async def _list_entities(
        self, table: str, user_id: str, filters: dict | None = None, limit: int = 100
    ) -> list[dict]:
        db = await self._conn()
        try:
            cursor = await db.execute(
                f"SELECT data FROM {table} WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            )
            rows = await cursor.fetchall()
            results = [json.loads(r["data"]) for r in rows]

            if filters:
                for key, val in filters.items():
                    results = [r for r in results if r.get(key) == val]

            return results
        finally:
            await db.close()

    async def _delete_entity(self, table: str, entity_id: str) -> bool:
        db = await self._conn()
        try:
            cursor = await db.execute(
                f"DELETE FROM {table} WHERE id = ?", (entity_id,)
            )
            await db.commit()
            return cursor.rowcount > 0
        finally:
            await db.close()

    async def _update_entity(self, table: str, entity_id: str, updates: dict) -> bool:
        db = await self._conn()
        try:
            cursor = await db.execute(
                f"SELECT data FROM {table} WHERE id = ?", (entity_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return False
            data = json.loads(row["data"])
            data.update(updates)
            data["updated_at"] = _utcnow()
            await db.execute(
                f"UPDATE {table} SET data = ?, updated_at = ? WHERE id = ?",
                (json.dumps(data, default=str), _utcnow(), entity_id),
            )
            await db.commit()
            return True
        finally:
            await db.close()

    # ── Required: User Data ───────────────────────────────────

    async def get_user(self, user_id: str) -> dict | None:
        db = await self._conn()
        try:
            cursor = await db.execute(
                "SELECT data FROM users WHERE id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return json.loads(row["data"])
            # Auto-create user on first access (standalone mode)
            data = {"id": user_id, "name": user_id, "created_at": _utcnow()}
            await db.execute(
                "INSERT OR IGNORE INTO users (id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, json.dumps(data), _utcnow(), _utcnow()),
            )
            await db.commit()
            return data
        finally:
            await db.close()

    async def get_balance(self, user_id: str) -> dict:
        return {"balance": 0.0, "currency": "USD"}

    # ── Required: Order Data ──────────────────────────────────

    async def get_orders(
        self, user_id: str, status: str | None = None,
        order_type: str | None = None, limit: int = 10,
    ) -> list[dict]:
        return []

    async def get_order(self, order_id: str) -> dict | None:
        return None

    # ── Required: Conversation Persistence ────────────────────

    async def save_conversation(
        self, conversation_id: str, user_id: str,
        messages: list[dict], title: str = "",
    ) -> None:
        db = await self._conn()
        try:
            now = _utcnow()
            await db.execute("""
                INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
            """, (conversation_id, user_id, title, now, now))

            for msg in messages:
                await db.execute("""
                    INSERT INTO messages (conversation_id, role, content, tools_used, data, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    conversation_id,
                    msg.get("role", ""),
                    msg.get("content", ""),
                    json.dumps(msg.get("tools_used", [])),
                    json.dumps(msg.get("data")) if msg.get("data") else None,
                    msg.get("timestamp", now),
                ))
            await db.commit()
        finally:
            await db.close()

    async def load_conversation(self, conversation_id: str) -> list[dict]:
        db = await self._conn()
        try:
            cursor = await db.execute(
                "SELECT role, content, tools_used, data, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp",
                (conversation_id,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "tools_used": json.loads(r["tools_used"]) if r["tools_used"] else [],
                    "data": json.loads(r["data"]) if r["data"] else None,
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]
        finally:
            await db.close()

    async def list_conversations(self, user_id: str, limit: int = 20) -> list[dict]:
        db = await self._conn()
        try:
            cursor = await db.execute("""
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = await cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "message_count": r["message_count"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        finally:
            await db.close()

    async def generate_id(self) -> str:
        return self._gen_id()

    # ── Agent Management ──────────────────────────────────────

    async def save_agent(self, user_id: str, agent_data: dict) -> str:
        return await self._save_entity("agents", agent_data.get("id"), user_id, agent_data)

    async def get_agent(self, agent_id: str) -> dict | None:
        return await self._get_entity("agents", agent_id)

    async def list_agents(self, user_id: str) -> list[dict]:
        return await self._list_entities("agents", user_id)

    async def delete_agent(self, agent_id: str) -> bool:
        return await self._delete_entity("agents", agent_id)

    # ── Agent Memory ──────────────────────────────────────────

    async def save_agent_memory(
        self, agent_id: str, key: str, value: str,
        category: str = "general", source: str = "agent", timestamp: str = "",
    ) -> None:
        db = await self._conn()
        try:
            await db.execute("""
                INSERT INTO agent_memories (agent_id, key, value, category, source, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id, key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    timestamp = excluded.timestamp
            """, (agent_id, key, value, category, source, timestamp or _utcnow()))
            await db.commit()
        finally:
            await db.close()

    async def load_agent_memories(
        self, agent_id: str, category: str | None = None
    ) -> list[dict]:
        db = await self._conn()
        try:
            if category:
                cursor = await db.execute(
                    "SELECT key, value, category, source, timestamp FROM agent_memories WHERE agent_id = ? AND category = ?",
                    (agent_id, category),
                )
            else:
                cursor = await db.execute(
                    "SELECT key, value, category, source, timestamp FROM agent_memories WHERE agent_id = ?",
                    (agent_id,),
                )
            return [dict(r) for r in await cursor.fetchall()]
        finally:
            await db.close()

    async def delete_agent_memory(self, agent_id: str, key: str) -> None:
        db = await self._conn()
        try:
            await db.execute(
                "DELETE FROM agent_memories WHERE agent_id = ? AND key = ?",
                (agent_id, key),
            )
            await db.commit()
        finally:
            await db.close()

    async def clear_agent_memories(self, agent_id: str) -> None:
        db = await self._conn()
        try:
            await db.execute("DELETE FROM agent_memories WHERE agent_id = ?", (agent_id,))
            await db.commit()
        finally:
            await db.close()

    # ── Brain Box Memory ──────────────────────────────────────

    async def save_brain_memory(
        self, namespace: str, key: str, value: str,
        category: str = "fact", metadata: dict | None = None,
    ) -> None:
        db = await self._conn()
        try:
            now = _utcnow()
            await db.execute("""
                INSERT INTO brain_memories_store (namespace, key, value, category, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
            """, (namespace, key, value, category, json.dumps(metadata or {}), now, now))
            await db.commit()
        finally:
            await db.close()

    async def load_brain_memories(
        self, namespace: str, category: str | None = None,
    ) -> list[dict]:
        db = await self._conn()
        try:
            if category:
                cursor = await db.execute(
                    "SELECT key, value, category, metadata FROM brain_memories_store WHERE namespace = ? AND category = ?",
                    (namespace, category),
                )
            else:
                cursor = await db.execute(
                    "SELECT key, value, category, metadata FROM brain_memories_store WHERE namespace = ?",
                    (namespace,),
                )
            return [
                {
                    "key": r["key"], "value": r["value"],
                    "category": r["category"],
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                }
                for r in await cursor.fetchall()
            ]
        finally:
            await db.close()

    async def delete_brain_memory(self, namespace: str, key: str) -> None:
        db = await self._conn()
        try:
            await db.execute(
                "DELETE FROM brain_memories_store WHERE namespace = ? AND key = ?",
                (namespace, key),
            )
            await db.commit()
        finally:
            await db.close()

    async def clear_brain_namespace(self, namespace: str) -> None:
        db = await self._conn()
        try:
            await db.execute("DELETE FROM brain_memories_store WHERE namespace = ?", (namespace,))
            await db.commit()
        finally:
            await db.close()

    # ── Datasets ──────────────────────────────────────────────

    async def save_dataset_metadata(self, user_id: str, dataset: dict) -> str:
        return await self._save_entity("datasets", dataset.get("id"), user_id, dataset)

    async def list_datasets(self, user_id: str) -> list[dict]:
        return await self._list_entities("datasets", user_id)

    async def get_dataset(self, dataset_id: str) -> dict | None:
        return await self._get_entity("datasets", dataset_id)

    async def delete_dataset(self, dataset_id: str) -> bool:
        return await self._delete_entity("datasets", dataset_id)

    # ── Todos ─────────────────────────────────────────────────

    async def save_todo(self, user_id: str, todo: dict) -> str:
        return await self._save_entity("todos", todo.get("id"), user_id, todo)

    async def list_todos(self, user_id: str, status: str | None = None) -> list[dict]:
        results = await self._list_entities("todos", user_id)
        if status:
            results = [t for t in results if t.get("status") == status]
        return results

    async def update_todo(self, todo_id: str, updates: dict) -> bool:
        return await self._update_entity("todos", todo_id, updates)

    async def delete_todo(self, todo_id: str) -> bool:
        return await self._delete_entity("todos", todo_id)

    # ── Notes ─────────────────────────────────────────────────

    async def save_note(self, user_id: str, note: dict) -> str:
        return await self._save_entity("notes", note.get("id"), user_id, note)

    async def list_notes(self, user_id: str, limit: int = 20) -> list[dict]:
        return await self._list_entities("notes", user_id, limit=limit)

    async def get_note(self, note_id: str) -> dict | None:
        return await self._get_entity("notes", note_id)

    async def delete_note(self, note_id: str) -> bool:
        return await self._delete_entity("notes", note_id)

    # ── Events ────────────────────────────────────────────────

    async def save_event(self, user_id: str, event: dict) -> str:
        return await self._save_entity("events", event.get("id"), user_id, event)

    async def list_events(
        self, user_id: str, start: str | None = None, end: str | None = None,
    ) -> list[dict]:
        results = await self._list_entities("events", user_id)
        if start:
            results = [e for e in results if e.get("start_time", "") >= start]
        if end:
            results = [e for e in results if e.get("start_time", "") <= end]
        return results

    async def update_event(self, event_id: str, updates: dict) -> bool:
        return await self._update_entity("events", event_id, updates)

    async def delete_event(self, event_id: str) -> bool:
        return await self._delete_entity("events", event_id)

    # ── Emergencies ───────────────────────────────────────────

    async def save_emergency(self, emergency: dict) -> str:
        eid = emergency.get("id") or self._gen_id()
        now = _utcnow()
        emergency["id"] = eid
        db = await self._conn()
        try:
            await db.execute("""
                INSERT INTO emergencies (id, data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
            """, (eid, json.dumps(emergency, default=str), now, now))
            await db.commit()
            return eid
        finally:
            await db.close()

    async def list_emergencies(self, filters: dict | None = None) -> list[dict]:
        db = await self._conn()
        try:
            cursor = await db.execute(
                "SELECT data FROM emergencies ORDER BY updated_at DESC LIMIT 100"
            )
            rows = await cursor.fetchall()
            results = [json.loads(r["data"]) for r in rows]
            if filters:
                for key, val in filters.items():
                    results = [r for r in results if r.get(key) == val]
            return results
        finally:
            await db.close()

    async def update_emergency(self, emergency_id: str, updates: dict) -> bool:
        db = await self._conn()
        try:
            cursor = await db.execute(
                "SELECT data FROM emergencies WHERE id = ?", (emergency_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return False
            data = json.loads(row["data"])
            data.update(updates)
            await db.execute(
                "UPDATE emergencies SET data = ?, updated_at = ? WHERE id = ?",
                (json.dumps(data, default=str), _utcnow(), emergency_id),
            )
            await db.commit()
            return True
        finally:
            await db.close()

    # ── Vehicles ──────────────────────────────────────────────

    async def save_vehicle(self, user_id: str, vehicle: dict) -> str:
        return await self._save_entity("vehicles", vehicle.get("id"), user_id, vehicle)

    async def list_vehicles(self, user_id: str) -> list[dict]:
        return await self._list_entities("vehicles", user_id)

    async def save_vehicle_position(self, vehicle_id: str, position: dict) -> None:
        db = await self._conn()
        try:
            await db.execute(
                "INSERT INTO vehicle_positions (vehicle_id, data, recorded_at) VALUES (?, ?, ?)",
                (vehicle_id, json.dumps(position, default=str), _utcnow()),
            )
            await db.commit()
        finally:
            await db.close()

    async def get_vehicle_history(
        self, vehicle_id: str, start: str, end: str,
    ) -> list[dict]:
        db = await self._conn()
        try:
            cursor = await db.execute(
                "SELECT data, recorded_at FROM vehicle_positions WHERE vehicle_id = ? AND recorded_at BETWEEN ? AND ? ORDER BY recorded_at",
                (vehicle_id, start, end),
            )
            return [
                {**json.loads(r["data"]), "recorded_at": r["recorded_at"]}
                for r in await cursor.fetchall()
            ]
        finally:
            await db.close()

    # ── Alerts ────────────────────────────────────────────────

    async def save_alert(self, user_id: str, alert: dict) -> str:
        aid = alert.get("id") or self._gen_id()
        now = _utcnow()
        alert["id"] = aid
        db = await self._conn()
        try:
            await db.execute(
                "INSERT INTO alerts (id, user_id, alert_type, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (aid, user_id, alert.get("type", ""), json.dumps(alert, default=str), now),
            )
            await db.commit()
            return aid
        finally:
            await db.close()

    async def list_alerts(
        self, user_id: str, alert_type: str | None = None, limit: int = 50,
    ) -> list[dict]:
        db = await self._conn()
        try:
            if alert_type:
                cursor = await db.execute(
                    "SELECT data FROM alerts WHERE user_id = ? AND alert_type = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, alert_type, limit),
                )
            else:
                cursor = await db.execute(
                    "SELECT data FROM alerts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                )
            return [json.loads(r["data"]) for r in await cursor.fetchall()]
        finally:
            await db.close()

    # ── User Preferences ──────────────────────────────────────

    async def save_user_preferences(
        self, user_id: str, feature: str, preferences: dict,
    ) -> None:
        db = await self._conn()
        try:
            await db.execute("""
                INSERT INTO user_preferences (user_id, feature, preferences, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, feature) DO UPDATE SET
                    preferences = excluded.preferences,
                    updated_at = excluded.updated_at
            """, (user_id, feature, json.dumps(preferences), _utcnow()))
            await db.commit()
        finally:
            await db.close()

    async def get_user_preferences(
        self, user_id: str, feature: str | None = None,
    ) -> dict:
        db = await self._conn()
        try:
            if feature:
                cursor = await db.execute(
                    "SELECT preferences FROM user_preferences WHERE user_id = ? AND feature = ?",
                    (user_id, feature),
                )
                row = await cursor.fetchone()
                return json.loads(row["preferences"]) if row else {}
            else:
                cursor = await db.execute(
                    "SELECT feature, preferences FROM user_preferences WHERE user_id = ?",
                    (user_id,),
                )
                return {
                    r["feature"]: json.loads(r["preferences"])
                    for r in await cursor.fetchall()
                }
        finally:
            await db.close()
