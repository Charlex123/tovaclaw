"""
Universal IMAP/SMTP email provider — works with ANY email service.

No OAuth setup. No Google Console. No API keys.

Supports:
    - Gmail (imap.gmail.com / smtp.gmail.com) — use app password
    - Outlook/Hotmail (outlook.office365.com / smtp.office365.com)
    - Yahoo (imap.mail.yahoo.com / smtp.mail.yahoo.com) — use app password
    - ProtonMail Bridge (127.0.0.1:1143 / 127.0.0.1:1025)
    - Corporate Exchange (via IMAP)
    - Any IMAP/SMTP server

How users connect (SECURE — password never touches the chat):
    1. User says "connect my email" in chat
    2. Tova returns a link: POST /auth/email/connect
    3. User submits email + app password via that HTTPS form/endpoint
    4. Credentials are encrypted at rest with Fernet (AES-128-CBC)
    5. The LLM/chat never sees the password

Security:
    - Passwords NEVER flow through the chat or LLM
    - Credentials encrypted at rest using Fernet symmetric encryption
    - Encryption key from TOVA_ENCRYPTION_KEY env var or auto-generated
    - IMAP connections use SSL/TLS by default
    - App passwords are scoped (can be revoked without changing main password)
    - Connection tested before storing credentials
    - Disconnect endpoint to wipe stored credentials

Usage (developer):
    provider = IMAPEmailProvider(store=my_store)
    await provider.connect("user_123", {
        "email": "alice@gmail.com",
        "password": "xxxx xxxx xxxx xxxx",  # App password
    })
    emails = await provider.list_emails("user_123")
"""

from __future__ import annotations

import asyncio
import email as email_lib
import email.utils
import imaplib
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from tova_core.crypto import encrypt, decrypt, is_encrypted
from tova_core.providers.email import BaseEmailProvider
from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)

# Auto-detected server settings for common email providers
KNOWN_PROVIDERS: dict[str, dict[str, Any]] = {
    "gmail.com": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "name": "Gmail",
        "app_password_url": "https://myaccount.google.com/apppasswords",
        "note": "Use a Gmail App Password (not your regular password).",
    },
    "googlemail.com": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "name": "Gmail",
        "app_password_url": "https://myaccount.google.com/apppasswords",
    },
    "outlook.com": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "name": "Outlook",
    },
    "hotmail.com": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "name": "Outlook/Hotmail",
    },
    "live.com": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "name": "Microsoft Live",
    },
    "yahoo.com": {
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "name": "Yahoo",
        "app_password_url": "https://login.yahoo.com/account/security/app-passwords",
        "note": "Use a Yahoo App Password.",
    },
    "icloud.com": {
        "imap_host": "imap.mail.me.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.me.com",
        "smtp_port": 587,
        "name": "iCloud",
        "app_password_url": "https://appleid.apple.com/account/manage",
        "note": "Use an Apple App-Specific Password.",
    },
    "me.com": {
        "imap_host": "imap.mail.me.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.me.com",
        "smtp_port": 587,
        "name": "iCloud",
    },
    "protonmail.com": {
        "imap_host": "127.0.0.1",
        "imap_port": 1143,
        "smtp_host": "127.0.0.1",
        "smtp_port": 1025,
        "name": "ProtonMail",
        "note": "Requires ProtonMail Bridge running locally.",
        "ssl": False,
    },
    "zoho.com": {
        "imap_host": "imap.zoho.com",
        "imap_port": 993,
        "smtp_host": "smtp.zoho.com",
        "smtp_port": 587,
        "name": "Zoho Mail",
    },
    "aol.com": {
        "imap_host": "imap.aol.com",
        "imap_port": 993,
        "smtp_host": "smtp.aol.com",
        "smtp_port": 587,
        "name": "AOL",
    },
    "yandex.com": {
        "imap_host": "imap.yandex.com",
        "imap_port": 993,
        "smtp_host": "smtp.yandex.com",
        "smtp_port": 587,
        "name": "Yandex",
    },
}


def detect_email_provider(email_address: str) -> dict[str, Any]:
    """Auto-detect IMAP/SMTP settings from email domain."""
    domain = email_address.split("@")[-1].lower()
    if domain in KNOWN_PROVIDERS:
        return KNOWN_PROVIDERS[domain]
    # Default: try standard IMAP/SMTP on the domain
    return {
        "imap_host": f"imap.{domain}",
        "imap_port": 993,
        "smtp_host": f"smtp.{domain}",
        "smtp_port": 587,
        "name": domain,
        "note": f"Auto-detected settings for {domain}. If login fails, check your provider's IMAP/SMTP docs.",
    }


class IMAPEmailProvider(BaseEmailProvider):
    """Universal IMAP/SMTP email provider.

    Works with any email service that supports IMAP and SMTP.
    Auto-detects server settings from the user's email domain.
    """

    def __init__(self, store: BaseStore | None = None):
        self.store = store
        # user_id -> {email, password, imap_host, smtp_host, ...}
        self._connections: dict[str, dict[str, Any]] = {}

    async def connect(self, user_id: str, credentials: dict) -> bool:
        """Connect a user's email account.

        Args:
            credentials: {
                "email": "alice@gmail.com",
                "password": "app-password-here",
                # Optional overrides:
                "imap_host": "...", "imap_port": 993,
                "smtp_host": "...", "smtp_port": 587,
            }
        """
        email_addr = credentials.get("email", "")
        password = credentials.get("password", "")

        if not email_addr or not password:
            raise ValueError("Email address and password are required.")

        # Auto-detect provider settings
        detected = detect_email_provider(email_addr)

        config = {
            "email": email_addr,
            "password": password,
            "imap_host": credentials.get("imap_host", detected["imap_host"]),
            "imap_port": int(credentials.get("imap_port", detected["imap_port"])),
            "smtp_host": credentials.get("smtp_host", detected["smtp_host"]),
            "smtp_port": int(credentials.get("smtp_port", detected["smtp_port"])),
            "use_ssl": credentials.get("use_ssl", detected.get("ssl", True)),
            "provider_name": detected.get("name", ""),
        }

        # Test IMAP connection
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: _test_imap(config))
        except Exception as e:
            provider_info = detected.get("name", config["imap_host"])
            note = detected.get("note", "")
            app_url = detected.get("app_password_url", "")
            err_msg = f"Failed to connect to {provider_info}: {e}"
            if note:
                err_msg += f"\n{note}"
            if app_url:
                err_msg += f"\nCreate an app password: {app_url}"
            raise ConnectionError(err_msg)

        self._connections[user_id] = config

        # Persist with encrypted password — NEVER store plaintext
        if self.store:
            try:
                await self.store.save_user_preferences(
                    user_id, "email_imap", {
                        "email": email_addr,
                        "password_encrypted": encrypt(password),
                        "imap_host": config["imap_host"],
                        "imap_port": config["imap_port"],
                        "smtp_host": config["smtp_host"],
                        "smtp_port": config["smtp_port"],
                        "use_ssl": config["use_ssl"],
                        "provider_name": config["provider_name"],
                    }
                )
            except NotImplementedError:
                pass

        logger.info(
            f"Email connected: {email_addr} via {config['imap_host']} "
            f"for user {user_id[:16]}..."
        )
        return True

    async def _get_config(self, user_id: str) -> dict[str, Any]:
        """Load email config for a user, decrypting the password."""
        if user_id in self._connections:
            return self._connections[user_id]

        if self.store:
            try:
                prefs = await self.store.get_user_preferences(user_id)
                config = prefs.get("email_imap")
                if config and config.get("email"):
                    # Decrypt password if stored encrypted
                    if "password_encrypted" in config:
                        config["password"] = decrypt(config["password_encrypted"])
                        del config["password_encrypted"]
                    elif "password" in config and is_encrypted(config["password"]):
                        # Migration: old format with encrypted value in "password" field
                        config["password"] = decrypt(config["password"])
                    self._connections[user_id] = config
                    return config
            except (NotImplementedError, Exception):
                pass

        raise PermissionError(
            "Email not connected. Use the secure endpoint POST /auth/email/connect "
            "to connect your email account. Never share your password in chat."
        )

    def _imap_connect(self, config: dict) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """Create an authenticated IMAP connection."""
        if config.get("use_ssl", True):
            ctx = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(
                config["imap_host"], config["imap_port"], ssl_context=ctx
            )
        else:
            imap = imaplib.IMAP4(config["imap_host"], config["imap_port"])

        imap.login(config["email"], config["password"])
        return imap

    async def list_emails(
        self,
        user_id: str,
        folder: str = "inbox",
        limit: int = 50,
        unread_only: bool = False,
        query: str = "",
    ) -> list[dict]:
        """List emails via IMAP."""
        config = await self._get_config(user_id)
        loop = asyncio.get_event_loop()

        def _fetch():
            imap = self._imap_connect(config)
            try:
                # Map common folder names to IMAP names
                folder_map = {
                    "inbox": "INBOX",
                    "sent": '"[Gmail]/Sent Mail"' if "gmail" in config["imap_host"] else "Sent",
                    "drafts": '"[Gmail]/Drafts"' if "gmail" in config["imap_host"] else "Drafts",
                    "trash": '"[Gmail]/Trash"' if "gmail" in config["imap_host"] else "Trash",
                    "spam": '"[Gmail]/Spam"' if "gmail" in config["imap_host"] else "Junk",
                    "starred": '"[Gmail]/Starred"' if "gmail" in config["imap_host"] else "INBOX",
                }
                imap_folder = folder_map.get(folder.lower(), folder)
                status, _ = imap.select(imap_folder, readonly=True)
                if status != "OK":
                    # Fallback to INBOX
                    imap.select("INBOX", readonly=True)

                # Build search criteria
                criteria = []
                if unread_only:
                    criteria.append("UNSEEN")
                if query:
                    criteria.append(f'(OR SUBJECT "{query}" FROM "{query}" BODY "{query}")')
                search_str = " ".join(criteria) if criteria else "ALL"

                _, msg_nums = imap.search(None, search_str)
                msg_ids = msg_nums[0].split()

                # Get most recent emails (IMAP returns oldest first)
                msg_ids = msg_ids[-limit:] if msg_ids else []
                msg_ids.reverse()

                emails = []
                for msg_id in msg_ids:
                    _, msg_data = imap.fetch(msg_id, "(RFC822.HEADER FLAGS)")
                    if not msg_data or not msg_data[0]:
                        continue

                    raw_header = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
                    msg = email_lib.message_from_bytes(raw_header)

                    # Check flags
                    flags_data = msg_data[1] if len(msg_data) > 1 else b""
                    is_read = b"\\Seen" in (flags_data if isinstance(flags_data, bytes) else b"")

                    # Decode subject
                    subject = _decode_header(msg.get("Subject", ""))
                    from_addr = _decode_header(msg.get("From", ""))
                    to_addr = _decode_header(msg.get("To", ""))
                    date_str = msg.get("Date", "")

                    emails.append({
                        "id": msg_id.decode(),
                        "subject": subject,
                        "from": from_addr,
                        "to": to_addr,
                        "date": date_str,
                        "snippet": subject[:100],
                        "is_read": is_read,
                        "labels": [],
                    })

                return emails
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        return await loop.run_in_executor(None, _fetch)

    async def get_email(self, user_id: str, email_id: str) -> dict:
        """Get full email content via IMAP."""
        config = await self._get_config(user_id)
        loop = asyncio.get_event_loop()

        def _fetch_full():
            imap = self._imap_connect(config)
            try:
                imap.select("INBOX", readonly=True)
                _, msg_data = imap.fetch(email_id.encode(), "(RFC822)")
                if not msg_data or not msg_data[0]:
                    return None

                raw_email = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
                msg = email_lib.message_from_bytes(raw_email)

                body_text = ""
                body_html = ""
                attachments = []

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        disposition = str(part.get("Content-Disposition", ""))

                        if "attachment" in disposition:
                            attachments.append({
                                "filename": part.get_filename() or "attachment",
                                "mime_type": content_type,
                                "size": len(part.get_payload(decode=True) or b""),
                            })
                        elif content_type == "text/plain" and not body_text:
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset() or "utf-8"
                                body_text = payload.decode(charset, errors="replace")
                        elif content_type == "text/html" and not body_html:
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset() or "utf-8"
                                body_html = payload.decode(charset, errors="replace")
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        charset = msg.get_content_charset() or "utf-8"
                        body_text = payload.decode(charset, errors="replace")

                return {
                    "id": email_id,
                    "subject": _decode_header(msg.get("Subject", "")),
                    "from": _decode_header(msg.get("From", "")),
                    "to": _decode_header(msg.get("To", "")),
                    "cc": _decode_header(msg.get("Cc", "")),
                    "date": msg.get("Date", ""),
                    "body_text": body_text,
                    "body_html": body_html,
                    "attachments": attachments,
                    "labels": [],
                }
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        result = await loop.run_in_executor(None, _fetch_full)
        if not result:
            raise ValueError(f"Email {email_id} not found")
        return result

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
        """Send an email via SMTP."""
        config = await self._get_config(user_id)
        loop = asyncio.get_event_loop()

        def _send():
            if html:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body, "html"))
            else:
                msg = MIMEText(body, "plain")

            msg["From"] = config["email"]
            msg["To"] = ", ".join(to)
            msg["Subject"] = subject
            if cc:
                msg["Cc"] = ", ".join(cc)

            all_recipients = list(to) + (cc or []) + (bcc or [])

            if config.get("smtp_port") == 465:
                # Direct SSL
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    config["smtp_host"], config["smtp_port"], context=ctx
                ) as smtp:
                    smtp.login(config["email"], config["password"])
                    smtp.sendmail(config["email"], all_recipients, msg.as_string())
            else:
                # STARTTLS (port 587)
                with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as smtp:
                    smtp.ehlo()
                    if config.get("use_ssl", True):
                        ctx = ssl.create_default_context()
                        smtp.starttls(context=ctx)
                        smtp.ehlo()
                    smtp.login(config["email"], config["password"])
                    smtp.sendmail(config["email"], all_recipients, msg.as_string())

            return {"status": "sent"}

        await loop.run_in_executor(None, _send)
        logger.info(f"Email sent from {config['email']} to {to}")

        return {
            "message_id": f"sent_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "status": "sent",
        }

    async def mark_read(self, user_id: str, email_id: str) -> bool:
        """Mark email as read via IMAP."""
        config = await self._get_config(user_id)
        loop = asyncio.get_event_loop()

        def _mark():
            imap = self._imap_connect(config)
            try:
                imap.select("INBOX")
                imap.store(email_id.encode(), "+FLAGS", "\\Seen")
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        await loop.run_in_executor(None, _mark)
        return True

    async def move_email(
        self, user_id: str, email_id: str, folder: str
    ) -> bool:
        """Move email to a folder via IMAP COPY + DELETE."""
        config = await self._get_config(user_id)
        loop = asyncio.get_event_loop()

        def _move():
            imap = self._imap_connect(config)
            try:
                imap.select("INBOX")
                imap.copy(email_id.encode(), folder)
                imap.store(email_id.encode(), "+FLAGS", "\\Deleted")
                imap.expunge()
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        await loop.run_in_executor(None, _move)
        return True

    async def search_emails(
        self, user_id: str, query: str, limit: int = 20
    ) -> list[dict]:
        """Search emails by query."""
        return await self.list_emails(user_id, query=query, limit=limit)

    async def list_folders(self, user_id: str) -> list[dict]:
        """List IMAP folders/mailboxes."""
        config = await self._get_config(user_id)
        loop = asyncio.get_event_loop()

        def _list():
            imap = self._imap_connect(config)
            try:
                _, folder_list = imap.list()
                folders = []
                for item in (folder_list or []):
                    if not item:
                        continue
                    decoded = item.decode() if isinstance(item, bytes) else str(item)
                    # Parse IMAP folder line: (\\flags) "/" "name"
                    parts = decoded.rsplit('"', 2)
                    name = parts[-1].strip().strip('"') if len(parts) >= 2 else decoded
                    if not name:
                        name = decoded.split()[-1].strip('"')

                    folders.append({
                        "name": name,
                        "id": name,
                        "type": "system" if name.upper() in ("INBOX", "SENT", "TRASH", "DRAFTS", "JUNK") else "user",
                        "unread_count": 0,
                        "total_count": 0,
                    })
                return folders
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        return await loop.run_in_executor(None, _list)

    async def disconnect(self, user_id: str) -> bool:
        """Disconnect and wipe stored email credentials for a user."""
        self._connections.pop(user_id, None)
        if self.store:
            try:
                await self.store.save_user_preferences(user_id, "email_imap", {})
            except NotImplementedError:
                pass
        logger.info(f"Email disconnected for user {user_id[:16]}...")
        return True

    async def is_connected(self, user_id: str) -> bool:
        """Check if a user has email credentials stored (without loading password)."""
        if user_id in self._connections:
            return True
        if self.store:
            try:
                prefs = await self.store.get_user_preferences(user_id)
                config = prefs.get("email_imap", {})
                return bool(config.get("email"))
            except (NotImplementedError, Exception):
                pass
        return False

    @staticmethod
    def get_provider_info(email_address: str) -> dict:
        """Get provider information for an email address.

        Useful for telling the user what they need to do to connect.
        """
        detected = detect_email_provider(email_address)
        return {
            "provider": detected.get("name", "Unknown"),
            "imap_host": detected["imap_host"],
            "smtp_host": detected["smtp_host"],
            "note": detected.get("note", ""),
            "app_password_url": detected.get("app_password_url", ""),
            "needs_app_password": "app_password_url" in detected,
        }


def _test_imap(config: dict) -> None:
    """Test IMAP connection. Raises on failure."""
    if config.get("use_ssl", True):
        ctx = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(
            config["imap_host"], config["imap_port"], ssl_context=ctx
        )
    else:
        imap = imaplib.IMAP4(config["imap_host"], config["imap_port"])

    try:
        imap.login(config["email"], config["password"])
        imap.select("INBOX", readonly=True)
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _decode_header(value: str) -> str:
    """Decode MIME-encoded email header."""
    if not value:
        return ""
    try:
        parts = email_lib.header.decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)
    except Exception:
        return value
