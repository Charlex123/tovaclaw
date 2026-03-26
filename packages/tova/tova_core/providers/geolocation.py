"""
Abstract geolocation/GPS provider interface.

Implement this class to connect Tova to GPS tracking hardware or fleet APIs.
"""

from abc import ABC, abstractmethod


class BaseGeolocationProvider(ABC):
    """Geolocation provider for vehicle/fleet tracking."""

    @abstractmethod
    async def get_vehicle_position(self, vehicle_id: str) -> dict:
        """Get current position of a vehicle.

        Returns:
            {"vehicle_id": str, "lat": float, "lng": float, "speed": float,
             "heading": float, "timestamp": str}
        """
        ...

    @abstractmethod
    async def get_fleet_positions(self, fleet_id: str) -> list[dict]:
        """Get current positions of all vehicles in a fleet.

        Returns:
            List of position dicts (same format as get_vehicle_position)
        """
        ...

    async def get_route(
        self,
        origin: dict,
        destination: dict,
        waypoints: list[dict] | None = None,
    ) -> dict:
        """Calculate route between two points.

        Args:
            origin: {"lat": float, "lng": float}
            destination: {"lat": float, "lng": float}
            waypoints: Optional intermediate points

        Returns:
            {"distance_km": float, "duration_minutes": float, "polyline": str, "steps": list}
        """
        raise NotImplementedError

    async def check_geofence(
        self,
        position: dict,
        geofences: list[dict],
    ) -> list[dict]:
        """Check if a position violates any geofences.

        Args:
            position: {"lat": float, "lng": float}
            geofences: List of {"id", "name", "center_lat", "center_lng", "radius_km"}

        Returns:
            List of violated geofence dicts
        """
        raise NotImplementedError
