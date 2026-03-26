"""
Ethical Consent Framework — training data is never collected without explicit user consent.

Principles:
1. OPT-IN ONLY — data collection is off by default. Users must explicitly agree.
2. TRANSPARENCY — users can see exactly what data is collected and how it's used.
3. CONTROL — users can export, review, and delete their data at any time.
4. ANONYMIZATION — PII is stripped before data enters the training pipeline.
5. LOCAL-FIRST — training data stays on the local machine by default.
6. REVOCABLE — consent can be withdrawn at any time, triggering data deletion.

This module manages per-user consent state, PII anonymization, and data lifecycle.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiosqlite

from tova_core.config import get_settings

logger = logging.getLogger(__name__)


class ConsentStatus(str, Enum):
    NOT_ASKED = "not_asked"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"  # was granted, then revoked


class DataScope(str, Enum):
    """What categories of data the user has consented to share."""
    CONVERSATIONS = "conversations"  # chat messages + replies
    TOOL_USAGE = "tool_usage"  # which tools were called and how
    PREFERENCES = "preferences"  # learned preferences and patterns
    CORRECTIONS = "corrections"  # user corrections to Tova's behavior
    ALL = "all"


# ── PII Patterns ──────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_RE = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")
_IL_ID_RE = re.compile(r"\b\d{9}\b")  # Israeli ID number (9 digits)
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_DATE_OF_BIRTH_RE = re.compile(
    r"\b(?:born|dob|birthday|date of birth)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\b",
    re.IGNORECASE,
)

PII_PATTERNS = {
    "email": _EMAIL_RE,
    "phone": _PHONE_RE,
    "ssn": _SSN_RE,
    "credit_card": _CREDIT_CARD_RE,
    "national_id": _IL_ID_RE,
    "ip_address": _IP_RE,
    "dob": _DATE_OF_BIRTH_RE,
}


def anonymize_text(text: str) -> str:
    """Strip PII from text, replacing with type-tagged placeholders.

    Examples:
        "Call me at 054-123-4567" → "Call me at [PHONE_REDACTED]"
        "My email is john@example.com" → "My email is [EMAIL_REDACTED]"
    """
    result = text
    for pii_type, pattern in PII_PATTERNS.items():
        tag = f"[{pii_type.upper()}_REDACTED]"
        result = pattern.sub(tag, result)
    return result


def anonymize_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Anonymize all string fields in a training sample."""
    result = {}
    for key, value in sample.items():
        if isinstance(value, str):
            result[key] = anonymize_text(value)
        elif isinstance(value, list):
            result[key] = [anonymize_text(v) if isinstance(v, str) else v for v in value]
        elif isinstance(value, dict):
            result[key] = anonymize_sample(value)
        else:
            result[key] = value
    return result


def hash_user_id(user_id: str) -> str:
    """One-way hash a user ID for anonymized training data.

    Training samples reference this hash instead of the real user ID,
    so the model cannot memorize user identities.
    """
    return hashlib.sha256(f"tova_training_{user_id}".encode()).hexdigest()[:16]


class ConsentManager:
    """Manages per-user consent for training data collection.

    All consent state is stored in the same SQLite database as the learning engine,
    ensuring a single source of truth.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or self._default_db_path()
        self._initialized = False

    @staticmethod
    def _default_db_path() -> str:
        import os
        base = os.path.expanduser("~/.tova")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "learning.db")

    async def _ensure_tables(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS training_consent (
                    user_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'not_asked',
                    scopes TEXT NOT NULL DEFAULT '[]',
                    granted_at TEXT,
                    withdrawn_at TEXT,
                    last_updated TEXT NOT NULL,
                    consent_version INTEGER NOT NULL DEFAULT 1,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            await db.commit()
        self._initialized = True

    async def get_consent(self, user_id: str) -> dict[str, Any]:
        """Get the current consent status for a user."""
        await self._ensure_tables()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM training_consent WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "user_id": row["user_id"],
                    "status": ConsentStatus(row["status"]),
                    "scopes": json.loads(row["scopes"]),
                    "granted_at": row["granted_at"],
                    "withdrawn_at": row["withdrawn_at"],
                    "consent_version": row["consent_version"],
                }
            return {
                "user_id": user_id,
                "status": ConsentStatus.NOT_ASKED,
                "scopes": [],
                "granted_at": None,
                "withdrawn_at": None,
                "consent_version": 0,
            }

    async def grant_consent(
        self,
        user_id: str,
        scopes: list[DataScope] | None = None,
    ) -> dict[str, Any]:
        """Record that a user has granted consent for data collection.

        Args:
            user_id: The user granting consent.
            scopes: Which data categories the user consents to. Defaults to all.

        Returns:
            Updated consent record.
        """
        await self._ensure_tables()
        now = datetime.now(timezone.utc).isoformat()
        scope_list = [s.value for s in (scopes or [DataScope.ALL])]

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO training_consent (user_id, status, scopes, granted_at, last_updated, consent_version)
                VALUES (?, 'granted', ?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    status = 'granted',
                    scopes = excluded.scopes,
                    granted_at = excluded.granted_at,
                    withdrawn_at = NULL,
                    last_updated = excluded.last_updated,
                    consent_version = training_consent.consent_version + 1
            """, (user_id, json.dumps(scope_list), now, now))
            await db.commit()

        logger.info(f"Consent GRANTED for user {user_id}, scopes: {scope_list}")
        return await self.get_consent(user_id)

    async def withdraw_consent(self, user_id: str, delete_data: bool = True) -> dict[str, Any]:
        """Withdraw consent and optionally delete all collected training data.

        Args:
            user_id: The user withdrawing consent.
            delete_data: If True, also purge all training samples for this user.

        Returns:
            Updated consent record.
        """
        await self._ensure_tables()
        now = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                UPDATE training_consent SET
                    status = 'withdrawn',
                    withdrawn_at = ?,
                    last_updated = ?,
                    consent_version = consent_version + 1
                WHERE user_id = ?
            """, (now, now, user_id))

            if delete_data:
                # Delete all training samples for this user
                await db.execute(
                    "DELETE FROM training_samples WHERE user_hash = ?",
                    (hash_user_id(user_id),),
                )

            await db.commit()

        logger.info(f"Consent WITHDRAWN for user {user_id}, data_deleted={delete_data}")
        return await self.get_consent(user_id)

    async def is_collection_allowed(
        self,
        user_id: str,
        scope: DataScope = DataScope.CONVERSATIONS,
    ) -> bool:
        """Check if data collection is allowed for a user and scope.

        Returns False unless:
        1. Global training is enabled in settings
        2. User has explicitly granted consent
        3. The requested scope is within the user's consented scopes
        """
        settings = get_settings()

        # Master switch must be on
        if not settings.tova_training_enabled:
            return False

        # If consent not required (e.g., local single-user mode), allow
        if not settings.tova_training_consent_required:
            return True

        consent = await self.get_consent(user_id)
        if consent["status"] != ConsentStatus.GRANTED:
            return False

        # Check scope
        user_scopes = consent["scopes"]
        return DataScope.ALL.value in user_scopes or scope.value in user_scopes

    async def get_consent_prompt(self) -> str:
        """Get the consent request message to show users.

        This is the message Tova shows when asking for consent.
        It must be clear, honest, and non-coercive.
        """
        return (
            "I can learn and improve from our conversations to give you better, "
            "more personalized responses over time. Here's what that means:\n\n"
            "**What I collect:** Our conversation exchanges and how I use tools to help you.\n\n"
            "**What I do with it:** Train a custom AI model that gets better at understanding "
            "your needs. All personal information (emails, phone numbers, IDs) is automatically "
            "stripped before training.\n\n"
            "**Your data stays local:** Training data never leaves this machine.\n\n"
            "**You're in control:**\n"
            "- You can see what data I've collected at any time\n"
            "- You can export all your data\n"
            "- You can delete all your data and withdraw consent whenever you want\n"
            "- Tova works perfectly fine without this — it's entirely optional\n\n"
            "Would you like to opt in to help me learn and improve?"
        )

    async def export_user_data(self, user_id: str) -> list[dict[str, Any]]:
        """Export all training data collected for a user (GDPR-style data export)."""
        user_hash = hash_user_id(user_id)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM training_samples WHERE user_hash = ? ORDER BY created_at",
                (user_hash,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_user_data(self, user_id: str) -> int:
        """Delete all training data for a user (right to be forgotten).

        Returns the number of samples deleted.
        """
        user_hash = hash_user_id(user_id)
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM training_samples WHERE user_hash = ?",
                (user_hash,),
            )
            await db.commit()
            deleted = cursor.rowcount
        logger.info(f"Deleted {deleted} training samples for user {user_id}")
        return deleted
