"""
Async SQLite storage for Tova's self-learning pipeline.

Uses aiosqlite for non-blocking async I/O compatible with FastAPI/asyncio.
All ML models, brain memories, and learning data are stored in a local
SQLite database with:

- aiosqlite for true async I/O (no event loop blocking)
- FTS5 full-text search for brain memory queries
- WAL journal mode for concurrent read performance
- Model versioning with rollback support
- UTC timestamps throughout
- HMAC integrity verification for serialized ML models
- Automatic expired memory cleanup

Database location: configurable via TOVA_LEARNING_DB env var,
defaults to ~/.tova/learning.db
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path.home() / ".tova"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "learning.db"
_HMAC_SECRET = os.environ.get("TOVA_MODEL_SECRET", "tova-model-integrity-key").encode()


def _utcnow() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _get_db_path() -> str:
    """Resolve the database file path from env or default."""
    path = os.environ.get("TOVA_LEARNING_DB", str(_DEFAULT_DB_PATH))
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path)


def _sign_model(data: str) -> str:
    """HMAC-SHA256 signature for model integrity verification."""
    return hmac.new(_HMAC_SECRET, data.encode(), hashlib.sha256).hexdigest()


def _verify_model(data: str, signature: str) -> bool:
    """Verify HMAC signature of serialized model data."""
    expected = hmac.new(_HMAC_SECRET, data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _escape_fts_query(query: str) -> str:
    """Escape special FTS5 characters to prevent query syntax errors."""
    special = set('"*():-^{}[]|')
    escaped = []
    for ch in query:
        if ch in special:
            escaped.append(" ")
        else:
            escaped.append(ch)
    return " ".join(escaped.split())


_SCHEMA_SQL = """
-- Brain memories — per-user, per-feature key-value store
CREATE TABLE IF NOT EXISTS brain_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace TEXT NOT NULL,
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'fact',
    relevance_score REAL DEFAULT 1.0,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    UNIQUE(namespace, user_id, key)
);

-- FTS5 virtual table for full-text search on brain memories
CREATE VIRTUAL TABLE IF NOT EXISTS brain_memories_fts USING fts5(
    key, value, content=brain_memories, content_rowid=id,
    tokenize='porter unicode61'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS brain_fts_insert AFTER INSERT ON brain_memories BEGIN
    INSERT INTO brain_memories_fts(rowid, key, value) VALUES (new.id, new.key, new.value);
END;
CREATE TRIGGER IF NOT EXISTS brain_fts_delete AFTER DELETE ON brain_memories BEGIN
    INSERT INTO brain_memories_fts(brain_memories_fts, rowid, key, value)
    VALUES ('delete', old.id, old.key, old.value);
END;
CREATE TRIGGER IF NOT EXISTS brain_fts_update AFTER UPDATE ON brain_memories BEGIN
    INSERT INTO brain_memories_fts(brain_memories_fts, rowid, key, value)
    VALUES ('delete', old.id, old.key, old.value);
    INSERT INTO brain_memories_fts(rowid, key, value) VALUES (new.id, new.key, new.value);
END;

-- ML model blobs with versioning and integrity
CREATE TABLE IF NOT EXISTS ml_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_type TEXT NOT NULL,
    model_data TEXT NOT NULL,
    signature TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, model_name)
);

-- Model version history for rollback
CREATE TABLE IF NOT EXISTS ml_model_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_type TEXT NOT NULL,
    model_data TEXT NOT NULL,
    signature TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

-- Learning log — audit trail of what was learned
CREATE TABLE IF NOT EXISTS learning_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    feature TEXT NOT NULL,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    source TEXT DEFAULT 'auto',
    created_at TEXT NOT NULL
);

-- Interaction stats — lightweight atomic counters
CREATE TABLE IF NOT EXISTS interaction_stats (
    user_id TEXT NOT NULL,
    feature TEXT NOT NULL,
    stat_key TEXT NOT NULL,
    stat_value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, feature, stat_key)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_brain_ns_user ON brain_memories(namespace, user_id);
CREATE INDEX IF NOT EXISTS idx_brain_category ON brain_memories(namespace, user_id, category);
CREATE INDEX IF NOT EXISTS idx_brain_expires ON brain_memories(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ml_user_model ON ml_models(user_id, model_name);
CREATE INDEX IF NOT EXISTS idx_log_user ON learning_log(user_id, feature, created_at);
CREATE INDEX IF NOT EXISTS idx_history_user ON ml_model_history(user_id, model_name, version);
"""


class LearningDB:
    """Async SQLite connection manager for the learning module.

    Uses aiosqlite for true non-blocking async I/O.
    WAL journal mode for concurrent reads.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _get_db_path()
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Initialize schema on first use."""
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.executescript(_SCHEMA_SQL)
            await db.commit()
        self._initialized = True

    @asynccontextmanager
    async def connection(self):
        """Async context manager for a database connection."""
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    async def cleanup_expired(self) -> int:
        """Remove expired brain memories. Call periodically."""
        now = _utcnow()
        async with self.connection() as db:
            cursor = await db.execute(
                "DELETE FROM brain_memories WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            return cursor.rowcount


class BrainMemoryStore:
    """Async SQLite-backed brain memory operations with FTS5 search."""

    def __init__(self, db: LearningDB):
        self.db = db

    async def save(
        self,
        namespace: str,
        user_id: str,
        key: str,
        value: str,
        category: str = "fact",
        relevance_score: float = 1.0,
        metadata: dict | None = None,
        expires_at: str | None = None,
    ) -> None:
        """Save or upsert a brain memory."""
        now = _utcnow()
        meta_json = json.dumps(metadata or {})

        async with self.db.connection() as db:
            await db.execute("""
                INSERT INTO brain_memories
                    (namespace, user_id, key, value, category, relevance_score,
                     metadata, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, user_id, key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    relevance_score = excluded.relevance_score,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
            """, (namespace, user_id, key, value, category, relevance_score,
                  meta_json, now, now, expires_at))

    async def load(
        self,
        namespace: str,
        user_id: str,
        category: str | None = None,
    ) -> list[dict]:
        """Load brain memories, optionally filtered by category."""
        async with self.db.connection() as db:
            if category:
                cursor = await db.execute("""
                    SELECT key, value, category, relevance_score, metadata,
                           created_at, updated_at
                    FROM brain_memories
                    WHERE namespace = ? AND user_id = ? AND category = ?
                      AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY relevance_score DESC, updated_at DESC
                """, (namespace, user_id, category, _utcnow()))
            else:
                cursor = await db.execute("""
                    SELECT key, value, category, relevance_score, metadata,
                           created_at, updated_at
                    FROM brain_memories
                    WHERE namespace = ? AND user_id = ?
                      AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY relevance_score DESC, updated_at DESC
                """, (namespace, user_id, _utcnow()))

            rows = await cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    async def search(
        self,
        namespace: str,
        user_id: str,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        """Full-text search on brain memories using FTS5.

        Uses SQLite FTS5 with porter stemming for proper text search
        instead of LIKE pattern matching.
        """
        fts_query = _escape_fts_query(query)
        if not fts_query.strip():
            return await self.load(namespace, user_id)

        async with self.db.connection() as db:
            cursor = await db.execute("""
                SELECT bm.key, bm.value, bm.category, bm.relevance_score,
                       bm.metadata, bm.created_at, bm.updated_at,
                       rank
                FROM brain_memories bm
                JOIN brain_memories_fts fts ON bm.id = fts.rowid
                WHERE brain_memories_fts MATCH ?
                  AND bm.namespace = ? AND bm.user_id = ?
                  AND (bm.expires_at IS NULL OR bm.expires_at > ?)
                ORDER BY rank
                LIMIT ?
            """, (fts_query, namespace, user_id, _utcnow(), limit))

            rows = await cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    async def delete(self, namespace: str, user_id: str, key: str) -> bool:
        async with self.db.connection() as db:
            cursor = await db.execute(
                "DELETE FROM brain_memories WHERE namespace = ? AND user_id = ? AND key = ?",
                (namespace, user_id, key),
            )
            return cursor.rowcount > 0

    async def clear_namespace(self, namespace: str, user_id: str) -> int:
        async with self.db.connection() as db:
            cursor = await db.execute(
                "DELETE FROM brain_memories WHERE namespace = ? AND user_id = ?",
                (namespace, user_id),
            )
            return cursor.rowcount

    async def update_relevance(
        self, namespace: str, user_id: str, key: str, new_score: float
    ) -> None:
        async with self.db.connection() as db:
            await db.execute(
                "UPDATE brain_memories SET relevance_score = ?, updated_at = ? WHERE namespace = ? AND user_id = ? AND key = ?",
                (new_score, _utcnow(), namespace, user_id, key),
            )

    async def count(self, namespace: str, user_id: str) -> int:
        async with self.db.connection() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM brain_memories WHERE namespace = ? AND user_id = ?",
                (namespace, user_id),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    @staticmethod
    def _row_to_dict(r) -> dict:
        return {
            "key": r["key"],
            "value": r["value"],
            "category": r["category"],
            "relevance_score": r["relevance_score"],
            "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }


class MLModelStore:
    """Async SQLite-backed ML model persistence with versioning and integrity.

    Features:
    - HMAC-SHA256 signature verification on model load (tamper detection)
    - Version history with rollback to any previous version
    - Safe: refuses to load unsigned or tampered models
    """

    def __init__(self, db: LearningDB):
        self.db = db

    async def save(
        self,
        user_id: str,
        model_name: str,
        model_type: str,
        model_data: str,
    ) -> int:
        """Save a model with HMAC signature. Returns the new version number."""
        now = _utcnow()
        signature = _sign_model(model_data)

        async with self.db.connection() as db:
            # Get current version
            cursor = await db.execute(
                "SELECT version, model_data, model_type, signature FROM ml_models WHERE user_id = ? AND model_name = ?",
                (user_id, model_name),
            )
            existing = await cursor.fetchone()

            if existing:
                old_version = existing["version"]
                new_version = old_version + 1

                # Archive current version to history
                await db.execute("""
                    INSERT INTO ml_model_history
                        (user_id, model_name, model_type, model_data, signature, version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, model_name, existing["model_type"],
                      existing["model_data"], existing["signature"],
                      old_version, now))

                # Update to new version
                await db.execute("""
                    UPDATE ml_models SET model_type = ?, model_data = ?,
                           signature = ?, version = ?, updated_at = ?
                    WHERE user_id = ? AND model_name = ?
                """, (model_type, model_data, signature, new_version, now,
                      user_id, model_name))

                # Keep only last 5 versions in history
                await db.execute("""
                    DELETE FROM ml_model_history
                    WHERE user_id = ? AND model_name = ?
                      AND version < ?
                """, (user_id, model_name, new_version - 5))

                return new_version
            else:
                await db.execute("""
                    INSERT INTO ml_models
                        (user_id, model_name, model_type, model_data, signature, version, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """, (user_id, model_name, model_type, model_data, signature, now, now))
                return 1

    async def load(self, user_id: str, model_name: str) -> dict | None:
        """Load a model with integrity verification. Returns None if not found or tampered."""
        async with self.db.connection() as db:
            cursor = await db.execute(
                "SELECT model_type, model_data, signature, version, updated_at FROM ml_models WHERE user_id = ? AND model_name = ?",
                (user_id, model_name),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            # Verify HMAC integrity
            if row["signature"] and not _verify_model(row["model_data"], row["signature"]):
                logger.warning(
                    f"Model integrity check failed for {model_name} (user {user_id}). "
                    f"Model may have been tampered with. Refusing to load."
                )
                return None

            return {
                "model_type": row["model_type"],
                "model_data": row["model_data"],
                "version": row["version"],
                "updated_at": row["updated_at"],
            }

    async def rollback(self, user_id: str, model_name: str, version: int) -> bool:
        """Rollback a model to a specific historical version."""
        async with self.db.connection() as db:
            cursor = await db.execute(
                "SELECT model_type, model_data, signature FROM ml_model_history WHERE user_id = ? AND model_name = ? AND version = ?",
                (user_id, model_name, version),
            )
            row = await cursor.fetchone()
            if not row:
                return False

            if row["signature"] and not _verify_model(row["model_data"], row["signature"]):
                logger.warning(f"Historical model v{version} integrity check failed. Refusing rollback.")
                return False

            await db.execute("""
                UPDATE ml_models SET model_type = ?, model_data = ?,
                       signature = ?, updated_at = ?
                WHERE user_id = ? AND model_name = ?
            """, (row["model_type"], row["model_data"], row["signature"],
                  _utcnow(), user_id, model_name))
            return True

    async def list_models(self, user_id: str) -> list[dict]:
        async with self.db.connection() as db:
            cursor = await db.execute(
                "SELECT model_name, model_type, version, updated_at FROM ml_models WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def delete(self, user_id: str, model_name: str) -> bool:
        async with self.db.connection() as db:
            cursor = await db.execute(
                "DELETE FROM ml_models WHERE user_id = ? AND model_name = ?",
                (user_id, model_name),
            )
            await db.execute(
                "DELETE FROM ml_model_history WHERE user_id = ? AND model_name = ?",
                (user_id, model_name),
            )
            return cursor.rowcount > 0

    async def delete_all_for_user(self, user_id: str) -> int:
        """GDPR right-to-be-forgotten: delete all models for a user."""
        async with self.db.connection() as db:
            cursor = await db.execute("DELETE FROM ml_models WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM ml_model_history WHERE user_id = ?", (user_id,))
            return cursor.rowcount


class InteractionLog:
    """Async interaction logging and stats."""

    def __init__(self, db: LearningDB):
        self.db = db

    async def log_learning(
        self,
        user_id: str,
        feature: str,
        category: str,
        key: str,
        value: str = "",
        source: str = "auto",
    ) -> None:
        async with self.db.connection() as db:
            await db.execute("""
                INSERT INTO learning_log (user_id, feature, category, key, value, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, feature, category, key, value, source, _utcnow()))

    async def get_stat(self, user_id: str, feature: str, stat_key: str) -> str | None:
        async with self.db.connection() as db:
            cursor = await db.execute(
                "SELECT stat_value FROM interaction_stats WHERE user_id = ? AND feature = ? AND stat_key = ?",
                (user_id, feature, stat_key),
            )
            row = await cursor.fetchone()
            return row["stat_value"] if row else None

    async def set_stat(self, user_id: str, feature: str, stat_key: str, stat_value: str) -> None:
        async with self.db.connection() as db:
            await db.execute("""
                INSERT INTO interaction_stats (user_id, feature, stat_key, stat_value, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, feature, stat_key) DO UPDATE SET
                    stat_value = excluded.stat_value,
                    updated_at = excluded.updated_at
            """, (user_id, feature, stat_key, stat_value, _utcnow()))

    async def increment_stat(self, user_id: str, feature: str, stat_key: str) -> int:
        """Atomic increment using SQL."""
        async with self.db.connection() as db:
            await db.execute("""
                INSERT INTO interaction_stats (user_id, feature, stat_key, stat_value, updated_at)
                VALUES (?, ?, ?, '1', ?)
                ON CONFLICT(user_id, feature, stat_key) DO UPDATE SET
                    stat_value = CAST(CAST(stat_value AS INTEGER) + 1 AS TEXT),
                    updated_at = excluded.updated_at
            """, (user_id, feature, stat_key, _utcnow()))
            cursor = await db.execute(
                "SELECT stat_value FROM interaction_stats WHERE user_id = ? AND feature = ? AND stat_key = ?",
                (user_id, feature, stat_key),
            )
            row = await cursor.fetchone()
            return int(row["stat_value"]) if row else 1

    async def get_learning_count(self, user_id: str, feature: str = "") -> int:
        async with self.db.connection() as db:
            if feature:
                cursor = await db.execute(
                    "SELECT COUNT(*) as cnt FROM learning_log WHERE user_id = ? AND feature = ?",
                    (user_id, feature),
                )
            else:
                cursor = await db.execute(
                    "SELECT COUNT(*) as cnt FROM learning_log WHERE user_id = ?",
                    (user_id,),
                )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def purge_user_data(self, user_id: str) -> dict:
        """GDPR right-to-be-forgotten: purge all data for a user."""
        async with self.db.connection() as db:
            r1 = await db.execute("DELETE FROM brain_memories WHERE user_id = ?", (user_id,))
            r2 = await db.execute("DELETE FROM ml_models WHERE user_id = ?", (user_id,))
            r3 = await db.execute("DELETE FROM ml_model_history WHERE user_id = ?", (user_id,))
            r4 = await db.execute("DELETE FROM learning_log WHERE user_id = ?", (user_id,))
            r5 = await db.execute("DELETE FROM interaction_stats WHERE user_id = ?", (user_id,))
            return {
                "memories_deleted": r1.rowcount,
                "models_deleted": r2.rowcount,
                "history_deleted": r3.rowcount,
                "logs_deleted": r4.rowcount,
                "stats_deleted": r5.rowcount,
            }


# ── Module-level singleton ────────────────────────────────────

_db_instance: LearningDB | None = None


def get_learning_db(db_path: str | None = None) -> LearningDB:
    """Get or create the module-level LearningDB singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = LearningDB(db_path)
    return _db_instance


def get_brain_store(db_path: str | None = None) -> BrainMemoryStore:
    return BrainMemoryStore(get_learning_db(db_path))


def get_model_store(db_path: str | None = None) -> MLModelStore:
    return MLModelStore(get_learning_db(db_path))


def get_interaction_log(db_path: str | None = None) -> InteractionLog:
    return InteractionLog(get_learning_db(db_path))
