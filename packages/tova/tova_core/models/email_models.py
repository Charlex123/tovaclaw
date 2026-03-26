"""Data models for the Email Management system."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class EmailPriority(str, Enum):
    URGENT = "urgent"
    IMPORTANT = "important"
    NORMAL = "normal"
    LOW = "low"


class EmailConnectRequest(BaseModel):
    """Request to connect an email account."""
    provider: str = Field(..., description="Email provider: gmail, outlook, imap")
    credentials: dict = Field(..., description="Provider-specific credentials/tokens")


class EmailListRequest(BaseModel):
    """Request to list emails."""
    folder: str = "inbox"
    limit: int = Field(default=50, ge=1, le=200)
    unread_only: bool = False
    query: str = ""


class EmailResponse(BaseModel):
    """Single email response."""
    id: str
    subject: str
    sender: str
    to: list[str] = []
    date: str = ""
    snippet: str = ""
    body: str = ""
    is_read: bool = True
    labels: list[str] = []
    priority: str = "normal"
    attachments: list[dict] = []


class EmailCategorizeResponse(BaseModel):
    """Email categorization result."""
    email_id: str
    subject: str
    priority: str
    category: str  # "action_required", "informational", "social", "promotional"
    reason: str = ""


class EmailSendRequest(BaseModel):
    """Request to send an email."""
    to: list[str]
    subject: str
    body: str
    html: bool = False
    cc: list[str] = []
    bcc: list[str] = []
