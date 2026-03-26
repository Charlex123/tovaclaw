"""
GPS tracking and geofence monitoring.

Background worker that polls vehicle positions, checks geofences,
and generates alerts for violations.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime
from typing import Any

from tova_core.providers.store import BaseStore
from tova_core.providers.geolocation import BaseGeolocationProvider
from tova_core.providers.notifier import BaseNotifier

logger = logging.getLogger(__name__)


class GPSTracker:
    """Background GPS position tracker with geofence monitoring.

    Polls vehicle positions at a configurable interval and:
    1. Stores position history
    2. Checks geofence violations
    3. Monitors speed limits
    4. Generates alerts for violations
    """

    def __init__(
        self,
        geolocation: BaseGeolocationProvider,
        store: BaseStore,
        notifier: BaseNotifier | None = None,
        poll_interval: int = 30,
        speed_limit_kmh: float = 120.0,
    ):
        self.geolocation = geolocation
        self.store = store
        self.notifier = notifier
        self.poll_interval = poll_interval
        self.speed_limit_kmh = speed_limit_kmh
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the GPS tracking loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._track_loop())
        logger.info(f"GPS tracker started (interval: {self.poll_interval}s)")

    async def stop(self) -> None:
        """Stop the tracking loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("GPS tracker stopped")

    async def _track_loop(self) -> None:
        """Main tracking loop."""
        while self._running:
            try:
                await self._poll_all_vehicles()
            except Exception as e:
                logger.error(f"GPS tracker error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _poll_all_vehicles(self) -> None:
        """Poll positions for all tracked vehicles."""
        try:
            vehicles = await self.store.list_vehicles(user_id="__all__")
        except (NotImplementedError, Exception):
            return

        for vehicle in vehicles:
            vehicle_id = vehicle.get("id", "")
            if not vehicle_id or vehicle.get("status") == "offline":
                continue
            await self._poll_vehicle(vehicle)

    async def _poll_vehicle(self, vehicle: dict[str, Any]) -> None:
        """Poll and process a single vehicle's position."""
        vehicle_id = vehicle.get("id", "")
        try:
            position = await self.geolocation.get_vehicle_position(vehicle_id)
        except Exception as e:
            logger.debug(f"Failed to get position for vehicle {vehicle_id}: {e}")
            return

        if not position:
            return

        # Store position history
        try:
            await self.store.save_vehicle_position(vehicle_id, position)
        except (NotImplementedError, Exception):
            pass

        # Check speed
        speed = position.get("speed", 0)
        if speed > self.speed_limit_kmh:
            await self._speed_alert(vehicle, position)

        # Check geofences
        geofences = vehicle.get("geofences", [])
        if geofences:
            await self._check_geofences(vehicle, position, geofences)

    async def _speed_alert(
        self, vehicle: dict[str, Any], position: dict[str, Any]
    ) -> None:
        """Generate a speed violation alert."""
        alert = {
            "type": "vehicle",
            "source": f"vehicle_{vehicle.get('id', '')}",
            "severity": "medium",
            "message": (
                f"Speed alert: {vehicle.get('name', 'Vehicle')} "
                f"({vehicle.get('plate', '')}) traveling at "
                f"{position.get('speed', 0):.0f} km/h"
            ),
            "data": {
                "vehicle_id": vehicle.get("id", ""),
                "speed": position.get("speed", 0),
                "lat": position.get("lat"),
                "lng": position.get("lng"),
            },
        }

        try:
            await self.store.save_alert(
                user_id=vehicle.get("user_id", ""),
                alert=alert,
            )
        except (NotImplementedError, Exception):
            pass

    async def _check_geofences(
        self,
        vehicle: dict[str, Any],
        position: dict[str, Any],
        geofences: list[dict],
    ) -> None:
        """Check if vehicle is outside any of its geofences."""
        lat = position.get("lat")
        lng = position.get("lng")
        if lat is None or lng is None:
            return

        for fence in geofences:
            center_lat = fence.get("center_lat", 0)
            center_lng = fence.get("center_lng", 0)
            radius_km = fence.get("radius_km", 1.0)

            distance = _haversine_km(lat, lng, center_lat, center_lng)
            if distance > radius_km:
                await self._geofence_alert(vehicle, position, fence, distance)

    async def _geofence_alert(
        self,
        vehicle: dict[str, Any],
        position: dict[str, Any],
        fence: dict[str, Any],
        distance_km: float,
    ) -> None:
        """Generate a geofence violation alert."""
        alert = {
            "type": "vehicle",
            "source": f"vehicle_{vehicle.get('id', '')}",
            "severity": "high",
            "message": (
                f"Geofence violation: {vehicle.get('name', 'Vehicle')} "
                f"({vehicle.get('plate', '')}) is {distance_km:.1f}km outside "
                f"'{fence.get('name', 'geofence')}'"
            ),
            "data": {
                "vehicle_id": vehicle.get("id", ""),
                "geofence_name": fence.get("name", ""),
                "distance_km": distance_km,
                "lat": position.get("lat"),
                "lng": position.get("lng"),
            },
        }

        try:
            await self.store.save_alert(
                user_id=vehicle.get("user_id", ""),
                alert=alert,
            )
        except (NotImplementedError, Exception):
            pass

        if self.notifier:
            try:
                await self.notifier.notify(
                    user_id=vehicle.get("user_id", ""),
                    title="Geofence Alert",
                    body=alert["message"],
                )
            except Exception:
                pass


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in kilometers."""
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
