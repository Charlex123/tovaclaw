"""
Email management tools.

Enable agents to read, categorize, summarize, and draft email replies.
"""

from __future__ import annotations

import logging
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.providers.email import BaseEmailProvider

logger = logging.getLogger(__name__)


def build_email_tools(
    store: BaseStore,
    email_provider: BaseEmailProvider,
) -> list:
    """Build email management tools using the provider pattern."""

    @tool
    async def list_emails(
        user_id: str,
        folder: str = "inbox",
        limit: int = 20,
        unread_only: bool = False,
    ) -> dict:
        """List emails from the user's inbox or a specific folder.

        Args:
            user_id: The user whose emails to list
            folder: Email folder: inbox, sent, drafts, trash, spam
            limit: Maximum number of emails to return
            unread_only: Only show unread emails
        """
        try:
            emails = await email_provider.list_emails(
                user_id=user_id,
                folder=folder,
                limit=limit,
                unread_only=unread_only,
            )
            return {
                "emails": [
                    {
                        "id": e.get("id", ""),
                        "subject": e.get("subject", "(no subject)"),
                        "from": e.get("from", ""),
                        "date": e.get("date", ""),
                        "snippet": e.get("snippet", ""),
                        "is_read": e.get("is_read", True),
                    }
                    for e in emails
                ],
                "count": len(emails),
                "folder": folder,
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def read_email(user_id: str, email_id: str) -> dict:
        """Read the full content of a specific email.

        Args:
            user_id: The user who owns the email
            email_id: The email ID to read
        """
        try:
            email = await email_provider.get_email(user_id, email_id)
            return {
                "id": email.get("id", ""),
                "subject": email.get("subject", ""),
                "from": email.get("from", ""),
                "to": email.get("to", []),
                "cc": email.get("cc", []),
                "date": email.get("date", ""),
                "body": email.get("body_text", email.get("body", "")),
                "attachments": [
                    {"name": a.get("name", ""), "type": a.get("content_type", "")}
                    for a in email.get("attachments", [])
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def categorize_emails(
        user_id: str,
        limit: int = 20,
    ) -> dict:
        """Categorize inbox emails by priority: urgent, important, normal, low.

        Analyzes email subjects, senders, and content to assign priority levels.

        Args:
            user_id: The user whose emails to categorize
            limit: Number of emails to categorize
        """
        try:
            emails = await email_provider.list_emails(
                user_id=user_id, folder="inbox", limit=limit, unread_only=True
            )

            categorized = []
            for e in emails:
                subject = e.get("subject", "").lower()
                sender = e.get("from", "").lower()

                # Simple heuristic categorization — agent can refine with LLM
                if any(w in subject for w in ["urgent", "asap", "emergency", "critical"]):
                    priority = "urgent"
                elif any(w in subject for w in ["important", "action required", "deadline"]):
                    priority = "important"
                elif any(w in subject for w in ["newsletter", "promo", "unsubscribe"]):
                    priority = "low"
                else:
                    priority = "normal"

                categorized.append({
                    "id": e.get("id", ""),
                    "subject": e.get("subject", ""),
                    "from": e.get("from", ""),
                    "priority": priority,
                    "date": e.get("date", ""),
                })

            # Sort by priority
            priority_order = {"urgent": 0, "important": 1, "normal": 2, "low": 3}
            categorized.sort(key=lambda x: priority_order.get(x["priority"], 2))

            return {"categorized_emails": categorized, "count": len(categorized)}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def draft_reply(
        user_id: str,
        email_id: str,
        tone: str = "professional",
    ) -> dict:
        """Read an email and prepare context for drafting a reply.

        The agent uses this context to generate an appropriate reply.

        Args:
            user_id: The user
            email_id: The email to reply to
            tone: Reply tone: professional, friendly, brief, formal
        """
        try:
            email = await email_provider.get_email(user_id, email_id)
            return {
                "original_subject": email.get("subject", ""),
                "original_from": email.get("from", ""),
                "original_body": email.get("body_text", "")[:5000],
                "tone": tone,
                "instruction": f"Draft a {tone} reply to this email.",
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def send_email(
        user_id: str,
        to: str,
        subject: str,
        body: str,
    ) -> dict:
        """Send an email on behalf of the user.

        Args:
            user_id: The user sending the email
            to: Recipient email address (comma-separated for multiple)
            subject: Email subject
            body: Email body text
        """
        try:
            recipients = [t.strip() for t in to.split(",") if t.strip()]
            result = await email_provider.send_email(
                user_id=user_id,
                to=recipients,
                subject=subject,
                body=body,
            )
            return {"success": True, "message_id": result.get("message_id", ""), "to": recipients}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def summarize_email_thread(
        user_id: str,
        email_id: str,
    ) -> dict:
        """Get an email thread's content for summarization.

        Args:
            user_id: The user
            email_id: Any email in the thread
        """
        try:
            email = await email_provider.get_email(user_id, email_id)
            return {
                "subject": email.get("subject", ""),
                "from": email.get("from", ""),
                "body": email.get("body_text", "")[:10000],
                "instruction": (
                    "Summarize this email thread. Include:\n"
                    "1. Main topic\n"
                    "2. Key decisions made\n"
                    "3. Action items\n"
                    "4. Open questions"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    return [list_emails, read_email, categorize_emails, draft_reply, send_email, summarize_email_thread]
