"""
Gmail email provider — OAuth2 + Gmail API.

Connects to users' Gmail accounts via OAuth2 for reading, sending,
and managing emails. Each user authorizes their own account.

Architecture:
    1. User initiates OAuth2 flow → Google consent screen
    2. Google returns authorization code → exchanged for tokens
    3. Tokens stored per-user in store (encrypted at rest)
    4. All email operations use the user's OAuth token

Usage:
    # Initialize with OAuth credentials
    provider = GmailProvider(
        client_id="...",
        client_secret="...",
        redirect_uri="http://localhost:8000/auth/gmail/callback",
        store=my_store,
    )

    # Or from env vars:
    GMAIL_CLIENT_ID=...
    GMAIL_CLIENT_SECRET=...
    GMAIL_REDIRECT_URI=...
    provider = GmailProvider(store=my_store)

    # Generate OAuth URL for a user
    url = provider.get_auth_url(user_id="session_abc123")

    # After user authorizes, exchange code for tokens
    await provider.handle_oauth_callback(user_id, code)

    # Now email operations work
    emails = await provider.list_emails(user_id, folder="inbox")

Install: pip install google-auth google-auth-httplib2 google-api-python-client
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

from tova_core.providers.email import BaseEmailProvider
from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)

# Gmail API scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]


class GmailProvider(BaseEmailProvider):
    """Gmail provider using OAuth2 + Google Gmail API.

    Per-user OAuth: each user authorizes their own Gmail account.
    Tokens are stored in the Tova store, keyed by user_id.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        store: BaseStore | None = None,
    ):
        self.client_id = client_id or os.environ.get("GMAIL_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GMAIL_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.environ.get(
            "GMAIL_REDIRECT_URI", "http://localhost:8000/auth/gmail/callback"
        )
        self.store = store
        # In-memory token cache: user_id -> credentials
        self._creds_cache: dict[str, Any] = {}

    def get_auth_url(self, user_id: str) -> str:
        """Generate the OAuth2 authorization URL for a user.

        Returns the URL to redirect the user to Google's consent screen.
        """
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=GMAIL_SCOPES,
        )
        flow.redirect_uri = self.redirect_uri

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=user_id,  # Pass user_id through OAuth state
        )
        return auth_url

    async def handle_oauth_callback(
        self, user_id: str, code: str
    ) -> bool:
        """Exchange OAuth authorization code for tokens and store them."""
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=GMAIL_SCOPES,
        )
        flow.redirect_uri = self.redirect_uri

        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: flow.fetch_token(code=code))

        creds = flow.credentials
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or []),
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        }

        # Store tokens
        if self.store:
            try:
                await self.store.save_user_preferences(
                    user_id, "gmail_oauth", token_data
                )
            except NotImplementedError:
                pass

        self._creds_cache[user_id] = creds
        logger.info(f"Gmail OAuth connected for user {user_id[:16]}...")
        return True

    async def _get_credentials(self, user_id: str):
        """Load OAuth credentials for a user."""
        if user_id in self._creds_cache:
            creds = self._creds_cache[user_id]
            # Refresh if expired
            if creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                import asyncio
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: creds.refresh(Request()))
                self._creds_cache[user_id] = creds
            return creds

        # Load from store
        if self.store:
            try:
                prefs = await self.store.get_user_preferences(user_id)
                token_data = prefs.get("gmail_oauth")
                if token_data:
                    from google.oauth2.credentials import Credentials
                    creds = Credentials(
                        token=token_data["token"],
                        refresh_token=token_data.get("refresh_token"),
                        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                        client_id=token_data.get("client_id", self.client_id),
                        client_secret=token_data.get("client_secret", self.client_secret),
                        scopes=token_data.get("scopes", GMAIL_SCOPES),
                    )
                    if creds.expired and creds.refresh_token:
                        from google.auth.transport.requests import Request
                        import asyncio
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, lambda: creds.refresh(Request()))
                    self._creds_cache[user_id] = creds
                    return creds
            except (NotImplementedError, Exception) as e:
                logger.debug(f"Could not load Gmail tokens for {user_id[:16]}: {e}")

        return None

    def _build_service(self, creds):
        """Build Gmail API service client."""
        from googleapiclient.discovery import build

        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    async def connect(self, user_id: str, credentials: dict) -> bool:
        """Connect using pre-existing OAuth tokens."""
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=credentials.get("token", ""),
            refresh_token=credentials.get("refresh_token"),
            token_uri=credentials.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=credentials.get("client_id", self.client_id),
            client_secret=credentials.get("client_secret", self.client_secret),
        )
        self._creds_cache[user_id] = creds
        return True

    async def list_emails(
        self,
        user_id: str,
        folder: str = "inbox",
        limit: int = 50,
        unread_only: bool = False,
        query: str = "",
    ) -> list[dict]:
        """List emails from Gmail using the API."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError(
                "Gmail not connected. Use /auth/gmail to authorize."
            )

        import asyncio
        loop = asyncio.get_event_loop()
        service = self._build_service(creds)

        # Build Gmail search query
        q_parts = []
        label_map = {
            "inbox": "INBOX", "sent": "SENT", "drafts": "DRAFT",
            "trash": "TRASH", "spam": "SPAM", "starred": "STARRED",
        }
        label = label_map.get(folder.lower(), folder.upper())
        q_parts.append(f"in:{folder}")
        if unread_only:
            q_parts.append("is:unread")
        if query:
            q_parts.append(query)
        q = " ".join(q_parts)

        # Fetch message list
        result = await loop.run_in_executor(
            None,
            lambda: service.users().messages().list(
                userId="me", q=q, maxResults=limit
            ).execute(),
        )

        messages = result.get("messages", [])
        emails = []

        # Fetch each message's metadata (batch)
        for msg_ref in messages[:limit]:
            msg = await loop.run_in_executor(
                None,
                lambda mid=msg_ref["id"]: service.users().messages().get(
                    userId="me", id=mid, format="metadata",
                    metadataHeaders=["Subject", "From", "To", "Date"],
                ).execute(),
            )
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            emails.append({
                "id": msg["id"],
                "thread_id": msg.get("threadId", ""),
                "subject": headers.get("Subject", "(no subject)"),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
                "is_read": "UNREAD" not in msg.get("labelIds", []),
                "labels": msg.get("labelIds", []),
            })

        return emails

    async def get_email(self, user_id: str, email_id: str) -> dict:
        """Get a single email's full content."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError("Gmail not connected.")

        import asyncio
        loop = asyncio.get_event_loop()
        service = self._build_service(creds)

        msg = await loop.run_in_executor(
            None,
            lambda: service.users().messages().get(
                userId="me", id=email_id, format="full"
            ).execute(),
        )

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        body_text = ""
        body_html = ""
        attachments = []

        # Extract body and attachments from MIME parts
        _extract_parts(msg.get("payload", {}), body_text, body_html, attachments, service, email_id, loop)

        # Get body from payload directly if not in parts
        payload = msg.get("payload", {})
        if not body_text and payload.get("body", {}).get("data"):
            body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

        return {
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "cc": headers.get("Cc", ""),
            "date": headers.get("Date", ""),
            "body_text": body_text,
            "body_html": body_html,
            "attachments": attachments,
            "labels": msg.get("labelIds", []),
        }

    async def send_email(
        self,
        user_id: str,
        to: list[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> dict:
        """Send an email via Gmail API."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError("Gmail not connected.")

        import asyncio
        loop = asyncio.get_event_loop()
        service = self._build_service(creds)

        if html:
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(body, "html"))
        else:
            message = MIMEText(body)

        message["to"] = ", ".join(to)
        message["subject"] = subject
        if cc:
            message["cc"] = ", ".join(cc)
        if bcc:
            message["bcc"] = ", ".join(bcc)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        sent = await loop.run_in_executor(
            None,
            lambda: service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute(),
        )

        logger.info(f"Email sent: {sent['id']} to {to}")
        return {
            "message_id": sent["id"],
            "thread_id": sent.get("threadId", ""),
            "status": "sent",
        }

    async def move_email(
        self, user_id: str, email_id: str, folder: str
    ) -> bool:
        """Move an email to a different label/folder."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError("Gmail not connected.")

        import asyncio
        loop = asyncio.get_event_loop()
        service = self._build_service(creds)

        label_map = {
            "inbox": "INBOX", "trash": "TRASH", "spam": "SPAM",
            "starred": "STARRED", "archive": None,
        }
        add_label = label_map.get(folder.lower(), folder.upper())

        body: dict[str, Any] = {}
        if folder.lower() == "archive":
            body["removeLabelIds"] = ["INBOX"]
        elif folder.lower() == "trash":
            body["addLabelIds"] = ["TRASH"]
            body["removeLabelIds"] = ["INBOX"]
        elif add_label:
            body["addLabelIds"] = [add_label]

        await loop.run_in_executor(
            None,
            lambda: service.users().messages().modify(
                userId="me", id=email_id, body=body
            ).execute(),
        )
        return True

    async def mark_read(self, user_id: str, email_id: str) -> bool:
        """Mark an email as read."""
        creds = await self._get_credentials(user_id)
        if not creds:
            return False

        import asyncio
        loop = asyncio.get_event_loop()
        service = self._build_service(creds)

        await loop.run_in_executor(
            None,
            lambda: service.users().messages().modify(
                userId="me", id=email_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute(),
        )
        return True

    async def search_emails(
        self, user_id: str, query: str, limit: int = 20
    ) -> list[dict]:
        """Search emails using Gmail search syntax."""
        return await self.list_emails(user_id, folder="all", limit=limit, query=query)

    async def list_folders(self, user_id: str) -> list[dict]:
        """List Gmail labels/folders."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError("Gmail not connected.")

        import asyncio
        loop = asyncio.get_event_loop()
        service = self._build_service(creds)

        result = await loop.run_in_executor(
            None,
            lambda: service.users().labels().list(userId="me").execute(),
        )

        folders = []
        for label in result.get("labels", []):
            detail = await loop.run_in_executor(
                None,
                lambda lid=label["id"]: service.users().labels().get(
                    userId="me", id=lid
                ).execute(),
            )
            folders.append({
                "name": label["name"],
                "id": label["id"],
                "type": label.get("type", "user"),
                "unread_count": detail.get("messagesUnread", 0),
                "total_count": detail.get("messagesTotal", 0),
            })

        return folders


def _extract_parts(payload, body_text, body_html, attachments, service, email_id, loop):
    """Recursively extract body and attachments from MIME payload."""
    parts = payload.get("parts", [])
    for part in parts:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain" and part.get("body", {}).get("data"):
            body_text += base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        elif mime_type == "text/html" and part.get("body", {}).get("data"):
            body_html += base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        elif part.get("filename"):
            attachments.append({
                "filename": part["filename"],
                "mime_type": mime_type,
                "size": part.get("body", {}).get("size", 0),
            })
        # Recurse into nested parts
        if part.get("parts"):
            _extract_parts(part, body_text, body_html, attachments, service, email_id, loop)
