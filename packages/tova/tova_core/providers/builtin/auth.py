"""
Built-in authentication providers — no external services required.

Four modes for four audiences:

1. SessionAuth — Anonymous sessions for regular users (DEFAULT)
   No signup, no login, no passwords. User opens the app and uses it.
   A session cookie auto-assigns a persistent anonymous identity.
   Tova learns and remembers per-session. Like using Google Maps
   without logging in — it just works.
   For: Regular people, consumer apps, public utilities.

2. NoAuth — Single-user / local mode
   No tokens, no passwords. Every request is "the user".
   For: Personal use, CLI tools, desktop apps, development.

3. APIKeyAuth — Developer / multi-tenant mode
   Developers authenticate with API keys (like OpenAI, Stripe, Anthropic).
   Keys stored in SQLite or provided via environment variable.
   For: Self-hosted services, small teams, developer integrations.

4. JWTAuth — Enterprise / custom auth mode
   Verifies JWTs with configurable secret/algorithm.
   Compatible with Auth0, Supabase, Firebase, Clerk, custom backends.
   For: Production services, enterprise deployments.

All four implement BaseAuth — swap them via config without touching code.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from tova_core.providers.auth import BaseAuth

logger = logging.getLogger(__name__)


class SessionAuth(BaseAuth):
    """Anonymous session-based auth — zero signup, zero friction.

    Regular users don't create accounts. They open Tova and use it.
    A session token is auto-generated on first visit and persisted
    via cookie. The session IS the identity — like using Google Maps
    without logging in.

    How it works:
        1. User visits Tova (no token) → server generates session_<random>
        2. Session ID returned as Set-Cookie + in response body
        3. Subsequent requests send session cookie → Tova recognizes them
        4. Brain Box, todos, notes, preferences all keyed to session ID

    Session tokens are cryptographically random (32 bytes hex = 64 chars).
    Sessions never expire by default (configurable via max_age_days).
    No passwords, no emails, no signup forms.

    Security model:
        - Session token = bearer of identity (like a browser cookie)
        - Sensitive features (email, CCTV) use external OAuth/pairing,
          not the session itself — session just holds the connection
        - If a user loses their session cookie, they start fresh
          (like clearing browser data on Google Maps)

    Usage:
        auth = SessionAuth()                           # defaults
        auth = SessionAuth(max_age_days=365)           # 1-year sessions
        auth = SessionAuth(cookie_name="tova_sid")     # custom cookie name
    """

    def __init__(
        self,
        max_age_days: int = 0,
        cookie_name: str = "tova_session",
    ):
        self.max_age_days = max_age_days  # 0 = never expires
        self.cookie_name = cookie_name

    @staticmethod
    def generate_session_id() -> str:
        """Generate a cryptographically random session ID."""
        return f"session_{secrets.token_hex(32)}"

    async def verify_token(self, token: str) -> str:
        """For SessionAuth, the token IS the user ID (the session ID).

        Any valid-format session token is accepted — there's no server-side
        session store to check against. The session ID is the identity.
        """
        if not token or not token.startswith("session_"):
            raise PermissionError("Invalid session token")
        return token

    def is_anonymous(self) -> bool:
        """SessionAuth users are always anonymous."""
        return True


class NoAuth(BaseAuth):
    """No authentication — single-user mode.

    Every request is treated as the same user. The token is ignored.
    Use this for personal instances, CLI tools, or development.

    The user_id defaults to "local_user" but can be configured.

    Usage:
        auth = NoAuth()                        # user_id = "local_user"
        auth = NoAuth(user_id="alice")         # user_id = "alice"
        TOVA_AUTH=none TOVA_USER_ID=alice      # via env vars
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id or os.environ.get("TOVA_USER_ID", "local_user")

    async def verify_token(self, token: str) -> str:
        return self.user_id


class APIKeyAuth(BaseAuth):
    """API key authentication — simple multi-user mode.

    Users send their API key as the Bearer token. Keys map to user IDs.
    Keys are hashed with SHA-256 before storage (never stored in plaintext).

    Key format: tova_<random_32_hex> (e.g., tova_a1b2c3d4e5f6...)

    There are three ways to provide keys:

    1. Constructor (embedded mode):
        auth = APIKeyAuth(keys={"tova_abc123": "user_1", "tova_def456": "user_2"})

    2. Environment variable (self-hosted mode):
        TOVA_API_KEYS=tova_abc123:user_1,tova_def456:user_2

    3. SQLite database (production mode):
        auth = APIKeyAuth(db_path="~/.tova/auth.db")
        key = await auth.create_key("user_1", name="Alice's laptop")

    Usage in requests:
        curl -H "Authorization: Bearer tova_abc123" http://localhost:8000/agent/chat
    """

    def __init__(
        self,
        keys: dict[str, str] | None = None,
        db_path: str | None = None,
    ):
        # In-memory key lookup: hash(key) → user_id
        self._keys: dict[str, str] = {}
        self._db_path = db_path

        # Load from constructor
        if keys:
            for key, uid in keys.items():
                self._keys[self._hash_key(key)] = uid

        # Load from env: TOVA_API_KEYS=key1:user1,key2:user2
        env_keys = os.environ.get("TOVA_API_KEYS", "")
        if env_keys:
            for entry in env_keys.split(","):
                entry = entry.strip()
                if ":" in entry:
                    key, uid = entry.split(":", 1)
                    self._keys[self._hash_key(key.strip())] = uid.strip()
                elif entry:
                    # Key without explicit user_id — derive user_id from key
                    self._keys[self._hash_key(entry)] = f"user_{entry[:8]}"

        self._db_initialized = False

    @staticmethod
    def _hash_key(key: str) -> str:
        """SHA-256 hash of a key — keys are never stored in plaintext."""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def generate_key() -> str:
        """Generate a new API key in tova_<hex> format."""
        return f"tova_{secrets.token_hex(24)}"

    async def _ensure_db(self) -> None:
        """Initialize SQLite for key storage if db_path is set."""
        if self._db_initialized or not self._db_path:
            return

        import aiosqlite
        from pathlib import Path

        db_path = Path(self._db_path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_apikey_user ON api_keys(user_id)"
            )
            await db.commit()
        self._db_initialized = True

    async def verify_token(self, token: str) -> str:
        """Verify an API key and return the associated user_id."""
        key_hash = self._hash_key(token)

        # Check in-memory keys first
        if key_hash in self._keys:
            return self._keys[key_hash]

        # Check SQLite if configured
        if self._db_path:
            await self._ensure_db()
            import aiosqlite

            async with aiosqlite.connect(str(self._db_path)) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT user_id FROM api_keys WHERE key_hash = ? AND is_active = 1",
                    (key_hash,),
                )
                row = await cursor.fetchone()
                if row:
                    # Update last_used timestamp
                    await db.execute(
                        "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
                        (datetime.now(timezone.utc).isoformat(), key_hash),
                    )
                    await db.commit()
                    # Cache for future lookups
                    self._keys[key_hash] = row["user_id"]
                    return row["user_id"]

        raise PermissionError("Invalid API key")

    async def create_key(
        self, user_id: str, name: str = ""
    ) -> dict[str, str]:
        """Create a new API key for a user. Returns the key (only shown once).

        Returns:
            {"key": "tova_...", "user_id": "...", "name": "..."}
        """
        key = self.generate_key()
        key_hash = self._hash_key(key)

        self._keys[key_hash] = user_id

        if self._db_path:
            await self._ensure_db()
            import aiosqlite

            async with aiosqlite.connect(str(self._db_path)) as db:
                await db.execute(
                    "INSERT INTO api_keys (key_hash, user_id, name, created_at) VALUES (?, ?, ?, ?)",
                    (key_hash, user_id, name, datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()

        return {"key": key, "user_id": user_id, "name": name}

    async def revoke_key(self, key: str) -> bool:
        """Revoke an API key. Returns True if found and revoked."""
        key_hash = self._hash_key(key)

        removed = key_hash in self._keys
        self._keys.pop(key_hash, None)

        if self._db_path:
            await self._ensure_db()
            import aiosqlite

            async with aiosqlite.connect(str(self._db_path)) as db:
                cursor = await db.execute(
                    "UPDATE api_keys SET is_active = 0 WHERE key_hash = ?",
                    (key_hash,),
                )
                await db.commit()
                removed = removed or cursor.rowcount > 0

        return removed

    async def list_keys(self, user_id: str) -> list[dict]:
        """List all active keys for a user (hashes only, not the actual keys)."""
        if not self._db_path:
            return [
                {"key_hash": kh[:16] + "...", "user_id": uid}
                for kh, uid in self._keys.items()
                if uid == user_id
            ]

        await self._ensure_db()
        import aiosqlite

        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT key_hash, name, created_at, last_used_at FROM api_keys WHERE user_id = ? AND is_active = 1",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "key_hash": row["key_hash"][:16] + "...",
                    "name": row["name"],
                    "created_at": row["created_at"],
                    "last_used_at": row["last_used_at"],
                }
                for row in rows
            ]


class JWTAuth(BaseAuth):
    """Standard JWT authentication — compatible with any JWT issuer.

    Verifies JWTs and extracts the user ID from a configurable claim.
    Works with Auth0, Supabase, Firebase, Clerk, Keycloak, or any
    service that issues standard JWTs.

    Configuration via constructor or env vars:
        TOVA_JWT_SECRET=your-secret-key
        TOVA_JWT_ALGORITHM=HS256
        TOVA_JWT_USER_CLAIM=sub          # Which claim holds the user ID

    Supported algorithms: HS256, HS384, HS512, RS256, RS384, RS512, ES256

    Usage:
        # HMAC (shared secret)
        auth = JWTAuth(secret="my-secret")

        # RSA (public key for verification only)
        auth = JWTAuth(secret=open("public.pem").read(), algorithm="RS256")

        # Auth0 / Supabase (auto-configured from env)
        TOVA_JWT_SECRET=<your-secret> tova serve
    """

    def __init__(
        self,
        secret: str | None = None,
        algorithm: str | None = None,
        user_claim: str | None = None,
        issuer: str | None = None,
        audience: str | None = None,
    ):
        self.secret = secret or os.environ.get("TOVA_JWT_SECRET", "")
        self.algorithm = algorithm or os.environ.get("TOVA_JWT_ALGORITHM", "HS256")
        self.user_claim = user_claim or os.environ.get("TOVA_JWT_USER_CLAIM", "sub")
        self.issuer = issuer or os.environ.get("TOVA_JWT_ISSUER", "")
        self.audience = audience or os.environ.get("TOVA_JWT_AUDIENCE", "")

    async def verify_token(self, token: str) -> str:
        """Verify JWT and extract user_id from the configured claim."""
        import jwt as pyjwt

        if not self.secret:
            raise PermissionError(
                "JWT secret not configured. Set TOVA_JWT_SECRET environment variable "
                "or pass secret= to JWTAuth()."
            )

        options: dict[str, Any] = {}
        kwargs: dict[str, Any] = {
            "algorithms": [self.algorithm],
        }

        if self.issuer:
            kwargs["issuer"] = self.issuer
        if self.audience:
            kwargs["audience"] = self.audience

        try:
            decoded = pyjwt.decode(token, self.secret, **kwargs)
        except pyjwt.ExpiredSignatureError:
            raise PermissionError("Token expired")
        except pyjwt.InvalidTokenError as e:
            raise PermissionError(f"Invalid token: {e}")

        user_id = decoded.get(self.user_claim)
        if not user_id:
            raise PermissionError(
                f"Token missing user claim '{self.user_claim}'. "
                f"Available claims: {list(decoded.keys())}. "
                f"Set TOVA_JWT_USER_CLAIM to the correct claim name."
            )

        return str(user_id)
