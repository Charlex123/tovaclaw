"""Data models for the Vehicle / Fleet Tracking system."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class VehicleStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class VehicleCreate(BaseModel):
    """Request to register a vehicle."""
    name: str = Field(..., min_length=1, max_length=200)
    plate: str = ""
    type: str = "car"  # car, truck, motorcycle, van, bus
    metadata: dict | None = None


class VehicleResponse(BaseModel):
    """Vehicle record response."""
    id: str
    user_id: str
    name: str
    plate: str = ""
    type: str = "car"
    status: str = "active"
    current_lat: float | None = None
    current_lng: float | None = None
    speed: float | None = None
    heading: float | None = None
    last_update: str = ""
    created_at: str = ""


class GeofenceCreate(BaseModel):
    """Request to create a geofence."""
    name: str = Field(..., min_length=1, max_length=200)
    center_lat: float
    center_lng: float
    radius_km: float = 1.0


class PositionResponse(BaseModel):
    """Vehicle position response."""
    vehicle_id: str
    lat: float
    lng: float
    speed: float = 0.0
    heading: float = 0.0
    timestamp: str = ""
