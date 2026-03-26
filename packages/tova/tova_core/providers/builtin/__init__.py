"""
Built-in provider implementations — zero-code setup for Tova.

These providers let anyone run Tova without writing Python code.
Just set environment variables and go.

Auth providers:
    - SessionAuth: Anonymous sessions for regular users (DEFAULT)
    - NoAuth: Single-user mode, no tokens needed
    - APIKeyAuth: Simple API key authentication (keys in SQLite)
    - JWTAuth: Standard JWT with configurable secret + algorithm

Store:
    - SQLiteStore: Full BaseStore implementation using local SQLite

Vector Store:
    - ChromaVectorStore: ChromaDB for RAG/dataset embeddings

Telephony:
    - TwilioTelephony: Phone calls + SMS via Twilio

Email:
    - GmailProvider: Gmail API with OAuth2

Calendar:
    - GoogleCalendarProvider: Google Calendar API with OAuth2

Video/CCTV:
    - RTSPVideoStream: OpenCV-based RTSP/HTTP camera capture

File Storage:
    - LocalFileStore: Local filesystem file management

Geolocation:
    - HTTPGeolocationProvider: REST API GPS tracking (Traccar, etc.)

Notifications:
    - StandaloneNotifier: In-app notifications + webhook delivery

Usage (standalone, no code):
    ANTHROPIC_API_KEY=sk-... tova

Usage (embedded, minimal code):
    from tova_core.providers.builtin import SessionAuth, SQLiteStore, ChromaVectorStore
    app = create_app(store=SQLiteStore(), auth=SessionAuth(), vector_store=ChromaVectorStore())
"""

from tova_core.providers.builtin.auth import SessionAuth, NoAuth, APIKeyAuth, JWTAuth
from tova_core.providers.builtin.store import SQLiteStore

# Lazy imports for optional-dependency providers
# These are imported explicitly to avoid ImportError when optional deps
# are not installed.

__all__ = [
    # Auth
    "SessionAuth", "NoAuth", "APIKeyAuth", "JWTAuth",
    # Store
    "SQLiteStore",
    # Optional (import directly from submodules)
    # "ChromaVectorStore", "TwilioTelephony", "GmailProvider",
    # "GoogleCalendarProvider", "RTSPVideoStream", "LocalFileStore",
    # "HTTPGeolocationProvider", "StandaloneNotifier",
]
