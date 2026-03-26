"""Data models for the Emergency Tracking & Alert system."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmergencyStatus(str, Enum):
    REPORTED = "reported"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class EmergencyCreate(BaseModel):
    """Request to report a new emergency."""
    type: str = Field(..., description="Emergency type: fire, medical, security, accident, natural_disaster, other")
    severity: str = "high"
    description: str = ""
    latitude: float | None = None
    longitude: float | None = None
    contact_numbers: list[str] = []
    metadata: dict | None = None


class EmergencyUpdate(BaseModel):
    """Request to update an emergency."""
    status: str | None = None
    severity: str | None = None
    description: str | None = None
    assigned_to: list[str] | None = None


class EmergencyResponse(BaseModel):
    """Emergency record response."""
    id: str
    reporter_id: str
    type: str
    severity: str
    description: str = ""
    status: str = "reported"
    latitude: float | None = None
    longitude: float | None = None
    assigned_to: list[str] = []
    escalation_level: int = 0
    contact_numbers: list[str] = []
    resolved_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


class AlertResponse(BaseModel):
    """Unified alert from any feature."""
    id: str
    user_id: str
    type: str  # "emergency", "cctv", "vehicle", "system"
    source: str
    severity: str
    message: str
    data: dict | None = None
    acknowledged: bool = False
    created_at: str = ""
