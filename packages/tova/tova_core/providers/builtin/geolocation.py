"""
HTTP-based geolocation provider — works with any GPS tracker API.

Connects to GPS tracking devices/services via HTTP REST APIs.
Compatible with Traccar (open-source), GPS Gateway, or any custom API.

For production fleets: use Geotab, Samsara, or Verizon Connect APIs.
For DIY tracking: use Traccar (https://www.traccar.org/) — free, self-hosted.

Usage:
    # Traccar (open-source fleet tracker):
    geo = HTTPGeolocationProvider(
        base_url="http://localhost:8082/api",
        auth_token="your-traccar-token",
    )

    # Custom GPS API:
    geo = HTTPGeolocationProvider(
        base_url="https://gps.mycompany.com/api/v1",
        auth_token="Bearer sk-...",
        vehicle_id_field="device_id",
    )

    # From env vars:
    TOVA_GPS_BASE_URL=http://localhost:8082/api
    TOVA_GPS_AUTH_TOKEN=...
    geo = HTTPGeolocationProvider()

    position = await geo.get_vehicle_position("truck-001")
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any

from tova_core.providers.geolocation import BaseGeolocationProvider

logger = logging.getLogger(__name__)


class HTTPGeolocationProvider(BaseGeolocationProvider):
    """HTTP REST API-based geolocation provider.

    Works with Traccar, GPS Gateway, or any REST API that returns
    vehicle positions as JSON. Configurable field mapping.
    """

    def __init__(
        self,
        base_url: str | None = None,
        auth_token: str | None = None,
        auth_header: str = "Authorization",
        # Field mapping (customize for your GPS API's JSON response)
        vehicle_id_field: str = "deviceId",
        lat_field: str = "latitude",
        lng_field: str = "longitude",
        speed_field: str = "speed",
        heading_field: str = "course",
        timestamp_field: str = "fixTime",
        # Endpoints (relative to base_url)
        positions_endpoint: str = "/positions",
        devices_endpoint: str = "/devices",
    ):
        self.base_url = (
            base_url
            or os.environ.get("TOVA_GPS_BASE_URL", "")
        ).rstrip("/")
        self.auth_token = auth_token or os.environ.get("TOVA_GPS_AUTH_TOKEN", "")
        self.auth_header = auth_header

        # Field mapping
        self.vehicle_id_field = vehicle_id_field
        self.lat_field = lat_field
        self.lng_field = lng_field
        self.speed_field = speed_field
        self.heading_field = heading_field
        self.timestamp_field = timestamp_field

        # Endpoints
        self.positions_endpoint = positions_endpoint
        self.devices_endpoint = devices_endpoint

        self._client = None

    async def _get_client(self):
        """Lazy-init httpx async client."""
        if self._client is None:
            import httpx
            headers = {}
            if self.auth_token:
                # Support both "Bearer token" and raw token
                if self.auth_token.startswith("Bearer "):
                    headers[self.auth_header] = self.auth_token
                else:
                    headers[self.auth_header] = f"Bearer {self.auth_token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=15.0,
            )
        return self._client

    async def get_vehicle_position(self, vehicle_id: str) -> dict:
        """Get current position of a vehicle from the GPS API."""
        if not self.base_url:
            raise RuntimeError(
                "GPS API not configured. Set TOVA_GPS_BASE_URL."
            )

        client = await self._get_client()

        # Fetch latest positions (most GPS APIs return all tracked devices)
        response = await client.get(
            self.positions_endpoint,
            params={"deviceId": vehicle_id},
        )
        response.raise_for_status()
        positions = response.json()

        # Handle both list and single object responses
        if isinstance(positions, dict):
            positions = [positions]

        # Find the position for this vehicle
        for pos in positions:
            pos_vehicle_id = str(pos.get(self.vehicle_id_field, ""))
            if pos_vehicle_id == str(vehicle_id):
                speed_raw = pos.get(self.speed_field, 0)
                # Convert knots to km/h if needed (Traccar reports in knots)
                speed_kmh = float(speed_raw) * 1.852 if speed_raw else 0.0

                return {
                    "vehicle_id": vehicle_id,
                    "lat": float(pos.get(self.lat_field, 0)),
                    "lng": float(pos.get(self.lng_field, 0)),
                    "speed": round(speed_kmh, 1),
                    "heading": float(pos.get(self.heading_field, 0)),
                    "timestamp": pos.get(self.timestamp_field, ""),
                    "attributes": pos.get("attributes", {}),
                }

        raise ValueError(f"No position found for vehicle '{vehicle_id}'")

    async def get_fleet_positions(self, fleet_id: str) -> list[dict]:
        """Get positions for all vehicles in a fleet."""
        if not self.base_url:
            raise RuntimeError("GPS API not configured.")

        client = await self._get_client()

        # Fetch all positions
        response = await client.get(self.positions_endpoint)
        response.raise_for_status()
        positions = response.json()

        if isinstance(positions, dict):
            positions = [positions]

        results = []
        for pos in positions:
            speed_raw = pos.get(self.speed_field, 0)
            speed_kmh = float(speed_raw) * 1.852 if speed_raw else 0.0
            results.append({
                "vehicle_id": str(pos.get(self.vehicle_id_field, "")),
                "lat": float(pos.get(self.lat_field, 0)),
                "lng": float(pos.get(self.lng_field, 0)),
                "speed": round(speed_kmh, 1),
                "heading": float(pos.get(self.heading_field, 0)),
                "timestamp": pos.get(self.timestamp_field, ""),
            })

        return results

    async def get_route(
        self,
        origin: dict,
        destination: dict,
        waypoints: list[dict] | None = None,
    ) -> dict:
        """Calculate route using OSRM (free, no API key needed).

        Falls back to straight-line distance if OSRM is unavailable.
        For production, use Google Maps Directions API or Mapbox.
        """
        import httpx

        coords = f"{origin['lng']},{origin['lat']};{destination['lng']},{destination['lat']}"
        if waypoints:
            wp_str = ";".join(f"{w['lng']},{w['lat']}" for w in waypoints)
            coords = f"{origin['lng']},{origin['lat']};{wp_str};{destination['lng']},{destination['lat']}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as osrm_client:
                response = await osrm_client.get(
                    f"https://router.project-osrm.org/route/v1/driving/{coords}",
                    params={"overview": "full", "steps": "true"},
                )
                response.raise_for_status()
                data = response.json()

                if data.get("routes"):
                    route = data["routes"][0]
                    return {
                        "distance_km": round(route["distance"] / 1000, 2),
                        "duration_minutes": round(route["duration"] / 60, 1),
                        "polyline": route.get("geometry", ""),
                        "steps": [
                            {
                                "instruction": step.get("maneuver", {}).get("instruction", ""),
                                "distance_m": step.get("distance", 0),
                                "duration_s": step.get("duration", 0),
                            }
                            for leg in route.get("legs", [])
                            for step in leg.get("steps", [])
                        ],
                    }
        except Exception as e:
            logger.warning(f"OSRM routing failed, using straight-line: {e}")

        # Fallback: straight-line distance
        dist = _haversine_km(
            origin["lat"], origin["lng"],
            destination["lat"], destination["lng"],
        )
        return {
            "distance_km": round(dist, 2),
            "duration_minutes": round(dist / 60 * 60, 1),  # Assume 60 km/h avg
            "polyline": "",
            "steps": [],
            "note": "Straight-line estimate (routing service unavailable)",
        }

    async def check_geofence(
        self,
        position: dict,
        geofences: list[dict],
    ) -> list[dict]:
        """Check if a position violates any geofences."""
        violations = []
        lat = position.get("lat", 0)
        lng = position.get("lng", 0)

        for fence in geofences:
            center_lat = fence.get("center_lat", 0)
            center_lng = fence.get("center_lng", 0)
            radius_km = fence.get("radius_km", 1.0)

            distance = _haversine_km(lat, lng, center_lat, center_lng)
            if distance > radius_km:
                violations.append({
                    **fence,
                    "distance_km": round(distance, 2),
                    "exceeded_by_km": round(distance - radius_km, 2),
                })

        return violations

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
