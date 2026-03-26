"""Data models for the Notes & Summarization system."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    """Request to create a new note."""
    title: str = Field(..., min_length=1, max_length=500)
    content: str = ""
    tags: list[str] = []
    source_type: str = ""  # "manual", "summary", "email", "meeting"
    source_url: str = ""


class NoteUpdate(BaseModel):
    """Request to update a note."""
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None


class NoteResponse(BaseModel):
    """Note response."""
    id: str
    user_id: str
    title: str
    content: str = ""
    summary: str = ""
    tags: list[str] = []
    source_type: str = ""
    source_url: str = ""
    created_at: str = ""
    updated_at: str = ""


class SummarizeRequest(BaseModel):
    """Request to summarize text content."""
    content: str = Field(..., min_length=1, max_length=50000)
    style: str = "concise"  # "concise", "detailed", "bullet_points", "executive"
    save_as_note: bool = False
    title: str = ""
