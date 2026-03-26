"""
Standalone Tova launcher — run Tova without writing any code.

This assembles a complete Tova application from environment variables.
No Python code required. Just configure and run.

Usage:
    # Default — uses local Ollama models (no API key needed):
    python -m tova_core.standalone

    # Single-user / local mode (simplest):
    TOVA_AUTH=none python -m tova_core.standalone

    # With Anthropic Claude (optional, for users who prefer proprietary):
    LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-... python -m tova_core.standalone

    # With API key auth:
    TOVA_AUTH=apikey TOVA_API_KEYS=tova_abc123:alice,tova_def456:bob \
    python -m tova_core.standalone

    # With JWT auth (Auth0, Supabase, etc.):
    TOVA_AUTH=jwt TOVA_JWT_SECRET=your-secret python -m tova_core.standalone

Prerequisites (for default local mode):
    1. Install Ollama: https://ollama.com/download
    2. Pull the default model: ollama pull qwen3:32b
    3. Start Ollama: ollama serve

Environment Variables:
    TOVA_AUTH          Auth mode: session (default), none, apikey, jwt
    TOVA_HOST          Bind address (default: 0.0.0.0)
    TOVA_PORT          Port (default: 8000)
    TOVA_STORE_DB      SQLite database path (default: ~/.tova/tova.db)
    TOVA_CORS_ORIGINS  Comma-separated CORS origins (default: *)

    # For auth=session (default):
    TOVA_SESSION_MAX_AGE_DAYS  Session lifetime in days (default: 0 = never expires)
    TOVA_SESSION_COOKIE        Cookie name (default: tova_session)

    # For auth=none:
    TOVA_USER_ID       Fixed user ID (default: local_user)

    # For auth=apikey:
    TOVA_API_KEYS      Comma-separated key:user_id pairs

    # For auth=jwt:
    TOVA_JWT_SECRET    JWT signing secret or public key
    TOVA_JWT_ALGORITHM Algorithm (default: HS256)
    TOVA_JWT_USER_CLAIM Claim containing user ID (default: sub)
"""

from __future__ import annotations

import logging
import os

from tova_core.app import create_app
from tova_core.providers.builtin.auth import SessionAuth, NoAuth, APIKeyAuth, JWTAuth
from tova_core.providers.builtin.store import SQLiteStore
from tova_core.tools.base import ToolRegistry

logger = logging.getLogger(__name__)


def _build_auth():
    """Build auth provider from TOVA_AUTH env var."""
    mode = os.environ.get("TOVA_AUTH", "session").lower().strip()

    if mode == "session":
        max_age = int(os.environ.get("TOVA_SESSION_MAX_AGE_DAYS", "0"))
        cookie = os.environ.get("TOVA_SESSION_COOKIE", "tova_session")
        logger.info("Auth mode: session (anonymous, no signup)")
        return SessionAuth(max_age_days=max_age, cookie_name=cookie)

    elif mode == "none":
        logger.info("Auth mode: none (single-user)")
        return NoAuth()

    elif mode == "apikey":
        db_path = os.environ.get("TOVA_AUTH_DB")
        auth = APIKeyAuth(db_path=db_path)
        key_count = len(auth._keys)
        logger.info(f"Auth mode: API key ({key_count} keys loaded)")
        return auth

    elif mode == "jwt":
        auth = JWTAuth()
        logger.info(f"Auth mode: JWT ({auth.algorithm}, claim={auth.user_claim})")
        return auth

    else:
        raise ValueError(
            f"Unknown TOVA_AUTH mode: '{mode}'. "
            f"Valid options: session, none, apikey, jwt"
        )


def _build_backend_factory():
    """Build a no-op backend factory for standalone mode.

    In standalone mode there's no external backend (Node.js, etc.).
    The agent relies entirely on its tools and the store.
    """
    from tova_core.providers.backend import BaseBackend

    class StandaloneBackend(BaseBackend):
        """No-op backend for standalone Tova."""

        async def search_products(self, query: str, **kwargs) -> list[dict]:
            return []

        async def create_order(self, user_id: str, **kwargs) -> dict:
            return {"error": "No backend configured"}

        async def close(self) -> None:
            pass

    return lambda token: StandaloneBackend()


def _build_optional_providers(store: SQLiteStore) -> dict:
    """Auto-detect and build optional providers from env vars.

    Each provider is initialized only if its required config is present.
    Missing optional dependencies are caught gracefully.
    """
    providers: dict = {}

    # ── Vector Store (ChromaDB for RAG) ───────────────────────
    try:
        from tova_core.providers.builtin.vector_store import ChromaVectorStore
        persist_path = os.environ.get("TOVA_VECTOR_DB_PATH", "~/.tova/vectordb")
        chroma_host = os.environ.get("TOVA_CHROMA_HOST", "")
        if chroma_host:
            providers["vector_store"] = ChromaVectorStore(
                host=chroma_host,
                port=int(os.environ.get("TOVA_CHROMA_PORT", "8000")),
            )
        else:
            providers["vector_store"] = ChromaVectorStore(persist_path=persist_path)
        logger.info("Vector store: ChromaDB enabled")
    except ImportError:
        logger.info("Vector store: not available (install chromadb)")

    # ── File Store (local filesystem) ─────────────────────────
    from tova_core.providers.builtin.file_store import LocalFileStore
    providers["file_store"] = LocalFileStore()
    logger.info("File store: local filesystem")

    # ── Notifier (in-app + webhook) ───────────────────────────
    from tova_core.providers.builtin.notifier import StandaloneNotifier
    providers["notifier"] = StandaloneNotifier(
        store=store,
        webhook_url=os.environ.get("TOVA_WEBHOOK_URL", ""),
    )
    if os.environ.get("TOVA_WEBHOOK_URL"):
        logger.info(f"Notifier: in-app + webhook")
    else:
        logger.info("Notifier: in-app only")

    # ── Telephony (Twilio) ────────────────────────────────────
    if os.environ.get("TWILIO_ACCOUNT_SID"):
        try:
            from tova_core.providers.builtin.telephony import TwilioTelephony
            providers["telephony"] = TwilioTelephony()
            logger.info("Telephony: Twilio enabled")
        except ImportError:
            logger.info("Telephony: Twilio configured but twilio package not installed")

    # ── Email ──────────────────────────────────────────────────
    # Gmail OAuth (if configured by deployer) or universal IMAP (always available)
    if os.environ.get("GMAIL_CLIENT_ID"):
        try:
            from tova_core.providers.builtin.email_provider import GmailProvider
            providers["email_provider"] = GmailProvider(store=store)
            logger.info("Email: Gmail OAuth enabled")
        except ImportError:
            logger.info("Email: Gmail configured but google-api-python-client not installed")

    if "email_provider" not in providers:
        # Universal IMAP — works with any email (Gmail, Outlook, Yahoo, etc.)
        # Users connect by providing their email + app password in chat.
        from tova_core.providers.builtin.imap_email import IMAPEmailProvider
        providers["email_provider"] = IMAPEmailProvider(store=store)
        logger.info("Email: Universal IMAP/SMTP (users connect in chat)")

    # ── Calendar ──────────────────────────────────────────────
    # Google Calendar (if configured by deployer) or local calendar (always available)
    if os.environ.get("GOOGLE_CALENDAR_CLIENT_ID"):
        try:
            from tova_core.providers.builtin.calendar_provider import GoogleCalendarProvider
            providers["calendar_provider"] = GoogleCalendarProvider(store=store)
            logger.info("Calendar: Google Calendar OAuth enabled")
        except ImportError:
            logger.info("Calendar: configured but google-api-python-client not installed")

    if "calendar_provider" not in providers:
        # Local calendar — always available, no external API
        from tova_core.providers.builtin.local_calendar import LocalCalendarProvider
        providers["calendar_provider"] = LocalCalendarProvider(store=store)
        logger.info("Calendar: Local (built-in, no setup needed)")

    # ── Video/CCTV (RTSP via OpenCV) ──────────────────────────
    if os.environ.get("TOVA_ENABLE_CCTV", "").lower() in ("1", "true", "yes"):
        try:
            from tova_core.providers.builtin.video_stream import RTSPVideoStream
            providers["video_stream"] = RTSPVideoStream(store=store)
            logger.info("CCTV: RTSP/OpenCV enabled")
        except ImportError:
            logger.info("CCTV: enabled but opencv-python not installed")

    # ── Geolocation (HTTP GPS API) ────────────────────────────
    if os.environ.get("TOVA_GPS_BASE_URL"):
        from tova_core.providers.builtin.geolocation import HTTPGeolocationProvider
        providers["geolocation"] = HTTPGeolocationProvider()
        logger.info(f"GPS: HTTP provider → {os.environ['TOVA_GPS_BASE_URL']}")

    # ── Travel / Flight Search (always available) ─────────────
    from tova_core.providers.builtin.travel_search import FlightSearchProvider
    providers["travel_provider"] = FlightSearchProvider()
    has_api = bool(os.environ.get("SERPAPI_API_KEY") or os.environ.get("AMADEUS_API_KEY"))
    logger.info(f"Travel: Flight search {'(live API)' if has_api else '(offline — set SERPAPI_API_KEY for live prices)'}")

    return providers


def create_standalone_app():
    """Create a fully configured Tova app from environment variables.

    This is the main entry point for non-developer deployments.
    Everything is configured via env vars — no Python code needed.

    Providers auto-enable based on available env vars:
        TWILIO_ACCOUNT_SID     → telephony (calls + SMS)
        GMAIL_CLIENT_ID        → email (Gmail OAuth)
        GOOGLE_CALENDAR_CLIENT_ID → calendar (Google Calendar)
        TOVA_ENABLE_CCTV=true  → video stream (RTSP cameras)
        TOVA_GPS_BASE_URL      → geolocation (fleet tracking)
        TOVA_WEBHOOK_URL       → webhook notifications (Slack, Discord, etc.)
    """
    auth = _build_auth()
    store = SQLiteStore()
    backend_factory = _build_backend_factory()
    tool_registry = ToolRegistry()
    optional = _build_optional_providers(store)

    cors_origins_str = os.environ.get("TOVA_CORS_ORIGINS", "*")
    cors_origins = [o.strip() for o in cors_origins_str.split(",")]

    app = create_app(
        backend_factory=backend_factory,
        store=store,
        auth=auth,
        tool_registry=tool_registry,
        cors_origins=cors_origins,
        notifier=optional.get("notifier"),
        vector_store=optional.get("vector_store"),
        file_store=optional.get("file_store"),
        telephony=optional.get("telephony"),
        email_provider=optional.get("email_provider"),
        calendar_provider=optional.get("calendar_provider"),
        video_stream=optional.get("video_stream"),
        geolocation=optional.get("geolocation"),
        travel_provider=optional.get("travel_provider"),
    )

    # Add standalone-specific endpoints

    @app.get("/auth/info")
    async def auth_info():
        """Show current auth configuration (no secrets)."""
        mode = os.environ.get("TOVA_AUTH", "session")
        info = {"mode": mode}
        if isinstance(auth, SessionAuth):
            info["cookie_name"] = auth.cookie_name
            info["note"] = (
                "Anonymous session mode. No signup required. "
                "A session cookie is auto-assigned on first visit."
            )
        elif isinstance(auth, NoAuth):
            info["user_id"] = auth.user_id
            info["note"] = "Single-user mode. All requests are this user."
        elif isinstance(auth, APIKeyAuth):
            info["keys_loaded"] = len(auth._keys)
            info["note"] = "Send API key as Bearer token."
        elif isinstance(auth, JWTAuth):
            info["algorithm"] = auth.algorithm
            info["user_claim"] = auth.user_claim
            info["note"] = "Send JWT as Bearer token."
        return info

    # ── OAuth Callback Endpoints (Gmail, Calendar) ──────────
    from fastapi import Header
    from fastapi.responses import HTMLResponse

    email_provider = optional.get("email_provider")
    calendar_provider = optional.get("calendar_provider")

    if email_provider:

        @app.get("/auth/gmail")
        async def gmail_auth_start(
            authorization: str = Header(""),
        ):
            """Start Gmail OAuth flow. Returns the authorization URL."""
            if authorization:
                token = authorization.replace("Bearer ", "")
                user_id = await auth.verify_token(token)
            else:
                user_id = "anonymous"
            url = email_provider.get_auth_url(user_id)
            return {"auth_url": url, "note": "Redirect the user to this URL."}

        @app.get("/auth/gmail/callback")
        async def gmail_auth_callback(code: str, state: str = ""):
            """Gmail OAuth callback — exchanges code for tokens."""
            user_id = state or "anonymous"
            success = await email_provider.handle_oauth_callback(user_id, code)
            return HTMLResponse(
                "<html><body><h2>Gmail connected!</h2>"
                "<p>You can close this tab and return to Tova.</p></body></html>"
                if success else
                "<html><body><h2>Failed to connect Gmail.</h2></body></html>"
            )

    # ── Secure Email Connect (IMAP — password never touches chat) ──
    from pydantic import BaseModel as _BaseModel

    class _EmailConnectRequest(_BaseModel):
        email: str
        password: str
        imap_host: str = ""
        imap_port: int = 0
        smtp_host: str = ""
        smtp_port: int = 0

    imap_provider = optional.get("email_provider")
    # Only add these endpoints for IMAP provider (has .connect method)
    if imap_provider and hasattr(imap_provider, "connect"):

        @app.post("/auth/email/connect")
        async def email_connect(
            req: _EmailConnectRequest,
            authorization: str = Header(""),
        ):
            """Securely connect an email account.

            Password is submitted via HTTPS to this endpoint — NEVER via chat.
            It's encrypted at rest and never visible to the AI.
            """
            if authorization:
                token = authorization.replace("Bearer ", "")
                user_id = await auth.verify_token(token)
            else:
                user_id = "anonymous"

            credentials = {"email": req.email, "password": req.password}
            if req.imap_host:
                credentials["imap_host"] = req.imap_host
                credentials["imap_port"] = req.imap_port
            if req.smtp_host:
                credentials["smtp_host"] = req.smtp_host
                credentials["smtp_port"] = req.smtp_port

            try:
                await imap_provider.connect(user_id, credentials)
            except (ConnectionError, ValueError) as e:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail=str(e))

            return {
                "status": "connected",
                "email": req.email,
                "note": "Your email is now connected. Credentials are encrypted at rest.",
            }

        @app.get("/auth/email/status")
        async def email_status(
            authorization: str = Header(""),
        ):
            """Check if email is connected (without exposing credentials)."""
            if authorization:
                token = authorization.replace("Bearer ", "")
                user_id = await auth.verify_token(token)
            else:
                user_id = "anonymous"

            connected = await imap_provider.is_connected(user_id)
            return {"connected": connected}

        @app.post("/auth/email/disconnect")
        async def email_disconnect(
            authorization: str = Header(""),
        ):
            """Disconnect email and wipe stored credentials."""
            if authorization:
                token = authorization.replace("Bearer ", "")
                user_id = await auth.verify_token(token)
            else:
                user_id = "anonymous"

            await imap_provider.disconnect(user_id)
            return {"status": "disconnected", "note": "All stored credentials have been wiped."}

        @app.get("/auth/email/providers")
        async def email_provider_info(email_address: str):
            """Get IMAP/SMTP settings for an email address.

            Returns server settings and whether an app password is needed.
            No credentials required — this is a public lookup.
            """
            from tova_core.providers.builtin.imap_email import IMAPEmailProvider
            return IMAPEmailProvider.get_provider_info(email_address)

    if calendar_provider:
        @app.get("/auth/calendar")
        async def calendar_auth_start(
            authorization: str = Header(""),
        ):
            """Start Google Calendar OAuth flow."""
            if authorization:
                token = authorization.replace("Bearer ", "")
                user_id = await auth.verify_token(token)
            else:
                user_id = "anonymous"
            url = calendar_provider.get_auth_url(user_id)
            return {"auth_url": url}

        @app.get("/auth/calendar/callback")
        async def calendar_auth_callback(code: str, state: str = ""):
            """Google Calendar OAuth callback."""
            user_id = state or "anonymous"
            success = await calendar_provider.handle_oauth_callback(user_id, code)
            return HTMLResponse(
                "<html><body><h2>Google Calendar connected!</h2>"
                "<p>You can close this tab and return to Tova.</p></body></html>"
                if success else
                "<html><body><h2>Failed to connect Calendar.</h2></body></html>"
            )

    # API key management endpoints (only for apikey auth)
    if isinstance(auth, APIKeyAuth):
        from fastapi import Header, HTTPException

        @app.post("/auth/keys")
        async def create_api_key(
            user_id: str,
            name: str = "",
            authorization: str = Header(""),
        ):
            """Create a new API key for a user.

            In standalone mode with apikey auth, the first key in TOVA_API_KEYS
            acts as an admin key that can create other keys.
            """
            if authorization:
                token = authorization.replace("Bearer ", "")
                try:
                    await auth.verify_token(token)
                except Exception:
                    raise HTTPException(status_code=401, detail="Invalid admin key")

            result = await auth.create_key(user_id, name)
            return {
                "key": result["key"],
                "user_id": result["user_id"],
                "name": result["name"],
                "warning": "Save this key — it cannot be retrieved after this response.",
            }

        @app.delete("/auth/keys")
        async def revoke_api_key(
            key: str,
            authorization: str = Header(...),
        ):
            """Revoke an API key."""
            token = authorization.replace("Bearer ", "")
            try:
                await auth.verify_token(token)
            except Exception:
                raise HTTPException(status_code=401, detail="Invalid admin key")

            revoked = await auth.revoke_key(key)
            return {"revoked": revoked}

    return app


# ── CLI entry point ──────────────────────────────────────────

def main():
    """Run Tova standalone server."""
    import uvicorn

    host = os.environ.get("TOVA_HOST", "0.0.0.0")
    port = int(os.environ.get("TOVA_PORT", "8000"))
    log_level = os.environ.get("LOG_LEVEL", "info").lower()

    from tova_core.config import get_settings as _get_settings
    _s = _get_settings()
    _llm_line = f"{_s.llm_provider} / {_s.agent_model}"

    print(f"""
╔══════════════════════════════════════════╗
║           Tova AI Agent Platform         ║
║                                          ║
║  Auth:    {os.environ.get('TOVA_AUTH', 'session'):<32}║
║  LLM:     {_llm_line:<32}║
║  Store:   SQLite                         ║
║  URL:     http://{host}:{port:<21}║
║  Docs:    http://{host}:{port}/docs{' ' * 13}║
║  Models:  http://{host}:{port}/models{' ' * 9}║
║                                          ║
║  Providers (auto-detected):              ║"""
    )
    _provider_flags = {
        "Twilio":   bool(os.environ.get("TWILIO_ACCOUNT_SID")),
        "Gmail":    bool(os.environ.get("GMAIL_CLIENT_ID")),
        "Calendar": bool(os.environ.get("GOOGLE_CALENDAR_CLIENT_ID")),
        "CCTV":     os.environ.get("TOVA_ENABLE_CCTV", "").lower() in ("1", "true", "yes"),
        "GPS":      bool(os.environ.get("TOVA_GPS_BASE_URL")),
        "Webhook":  bool(os.environ.get("TOVA_WEBHOOK_URL")),
        "Flights":  True,  # Always available (offline fallback if no API key)
    }
    for name, enabled in _provider_flags.items():
        status = "✓" if enabled else "·"
        print(f"║    {status} {name:<36}║")
    print("""\
║                                          ║
╚══════════════════════════════════════════╝
""")

    app = create_standalone_app()
    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
