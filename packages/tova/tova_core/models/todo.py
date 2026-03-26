"""Data models for the Todos / Task Planning system."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TodoCreate(BaseModel):
    """Request to create a new todo."""
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    priority: str = "medium"
    due_date: str | None = None
    tags: list[str] = []
    parent_id: str | None = None
    dependencies: list[str] = []


class TodoUpdate(BaseModel):
    """Request to update a todo."""
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    tags: list[str] | None = None


class TodoResponse(BaseModel):
    """Todo item response."""
    id: str
    user_id: str
    title: str
    description: str = ""
    status: str = "pending"
    priority: str = "medium"
    due_date: str | None = None
    tags: list[str] = []
    parent_id: str | None = None
    dependencies: list[str] = []
    completed_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
