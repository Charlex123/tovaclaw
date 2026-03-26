"""Data models for the Event Planning system."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    """Request to create a new event."""
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    start_time: str = Field(..., description="ISO datetime string")
    end_time: str = Field(..., description="ISO datetime string")
    location: str = ""
    attendees: list[str] = []
    reminders: list[dict] = []  # [{"minutes_before": 30, "method": "push"}]
    recurrence: str | None = None  # iCal RRULE format
    metadata: dict | None = None


class EventUpdate(BaseModel):
    """Request to update an event."""
    title: str | None = None
    description: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    attendees: list[str] | None = None
    reminders: list[dict] | None = None
    status: str | None = None


class EventResponse(BaseModel):
    """Event response."""
    id: str
    user_id: str
    title: str
    description: str = ""
    start_time: str
    end_time: str
    location: str = ""
    attendees: list[str] = []
    reminders: list[dict] = []
    status: str = "scheduled"  # scheduled, cancelled, completed
    recurrence: str | None = None
    created_at: str = ""
    updated_at: str = ""
