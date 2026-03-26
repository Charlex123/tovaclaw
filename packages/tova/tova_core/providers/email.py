"""
Abstract email provider interface.

Implement this class to connect Tova to email services.
Supports: Gmail API, Microsoft Graph, generic IMAP, etc.
"""

from abc import ABC, abstractmethod


class BaseEmailProvider(ABC):
    """Email provider for reading, sending, and managing emails.

    Each user connects their own email account via OAuth or credentials.
    All operations are scoped to the authenticated user.
    """

    @abstractmethod
    async def connect(self, user_id: str, credentials: dict) -> bool:
        """Connect/authenticate a user's email account.

        Args:
            user_id: Tova user ID
            credentials: Provider-specific credentials (OAuth tokens, IMAP config, etc.)

        Returns:
            True if connection successful
        """
        ...

    @abstractmethod
    async def list_emails(
        self,
        user_id: str,
        folder: str = "inbox",
        limit: int = 50,
        unread_only: bool = False,
        query: str = "",
    ) -> list[dict]:
        """List emails from a folder.

        Returns:
            List of dicts: [{id, subject, from, to, date, snippet, is_read, labels}]
        """
        ...

    @abstractmethod
    async def get_email(self, user_id: str, email_id: str) -> dict:
        """Get a single email's full content.

        Returns:
            {id, subject, from, to, cc, date, body_text, body_html, attachments, labels}
        """
        ...

    @abstractmethod
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
        """Send an email.

        Returns:
            {"message_id": str, "status": str}
        """
        ...

    async def move_email(
        self,
        user_id: str,
        email_id: str,
        folder: str,
    ) -> bool:
        """Move an email to a different folder. Returns True if moved."""
        raise NotImplementedError

    async def mark_read(self, user_id: str, email_id: str) -> bool:
        """Mark an email as read."""
        raise NotImplementedError

    async def search_emails(
        self,
        user_id: str,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        """Search emails by query string."""
        raise NotImplementedError

    async def list_folders(self, user_id: str) -> list[dict]:
        """List available email folders/labels.

        Returns:
            List of dicts: [{name, unread_count, total_count}]
        """
        raise NotImplementedError
