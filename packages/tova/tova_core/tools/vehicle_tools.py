"""
Vehicle / Fleet tracking tools.

Enable agents to track vehicles, monitor fleets, and check geofences.
"""

from __future__ import annotations

import logging
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.providers.geolocation import BaseGeolocationProvider

logger = logging.getLogger(__name__)


def build_vehicle_tools(
    store: BaseStore,
    geolocation: BaseGeolocationProvider,
) -> list:
    """Build vehicle/fleet tracking tools using the provider pattern."""

    @tool
    async def get_vehicle_position(vehicle_id: str) -> dict:
        """Get the current GPS position of a vehicle.

        Args:
            vehicle_id: The vehicle ID to locate
        """
        try:
            position = await geolocation.get_vehicle_position(vehicle_id)
            return {
                "vehicle_id": vehicle_id,
                "lat": position.get("lat"),
                "lng": position.get("lng"),
                "speed": position.get("speed", 0),
                "heading": position.get("heading", 0),
                "timestamp": position.get("timestamp", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def get_fleet_overview(user_id: str) -> dict:
        """Get current positions and status of all vehicles in the user's fleet.

        Args:
            user_id: The fleet owner's user ID
        """
        try:
            vehicles = await store.list_vehicles(user_id)
            fleet = []
            for v in vehicles:
                vehicle_id = v.get("id", "")
                entry = {
                    "id": vehicle_id,
                    "name": v.get("name", ""),
                    "plate": v.get("plate", ""),
                    "status": v.get("status", "unknown"),
                    "lat": v.get("current_lat"),
                    "lng": v.get("current_lng"),
                    "speed": v.get("speed"),
                    "last_update": v.get("last_update", ""),
                }
                fleet.append(entry)

            return {"vehicles": fleet, "count": len(fleet)}
        except NotImplementedError:
            return {"vehicles": [], "count": 0}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def get_vehicle_history(
        vehicle_id: str,
        start: str,
        end: str,
    ) -> dict:
        """Get GPS position history for a vehicle over a date range.

        Args:
            vehicle_id: The vehicle to get history for
            start: Start of range (ISO datetime)
            end: End of range (ISO datetime)
        """
        try:
            history = await store.get_vehicle_history(vehicle_id, start, end)
            return {
                "vehicle_id": vehicle_id,
                "positions": [
                    {
                        "lat": p.get("lat"),
                        "lng": p.get("lng"),
                        "speed": p.get("speed", 0),
                        "timestamp": p.get("timestamp", ""),
                    }
                    for p in history
                ],
                "count": len(history),
            }
        except NotImplementedError:
            return {"positions": [], "count": 0}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def check_geofence_violations(user_id: str) -> dict:
        """Check if any vehicles in the fleet are outside their geofences.

        Args:
            user_id: The fleet owner's user ID
        """
        try:
            vehicles = await store.list_vehicles(user_id)
            violations = []

            for v in vehicles:
                geofences = v.get("geofences", [])
                lat = v.get("current_lat")
                lng = v.get("current_lng")
                if not geofences or lat is None or lng is None:
                    continue

                try:
                    violated = await geolocation.check_geofence(
                        {"lat": lat, "lng": lng}, geofences
                    )
                    for fence in violated:
                        violations.append({
                            "vehicle_id": v.get("id", ""),
                            "vehicle_name": v.get("name", ""),
                            "geofence_name": fence.get("name", ""),
                            "lat": lat,
                            "lng": lng,
                        })
                except NotImplementedError:
                    pass

            return {"violations": violations, "count": len(violations)}
        except NotImplementedError:
            return {"violations": [], "count": 0}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def calculate_route(
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict:
        """Calculate the optimal route between two points.

        Args:
            origin_lat: Starting latitude
            origin_lng: Starting longitude
            dest_lat: Destination latitude
            dest_lng: Destination longitude
        """
        try:
            route = await geolocation.get_route(
                origin={"lat": origin_lat, "lng": origin_lng},
                destination={"lat": dest_lat, "lng": dest_lng},
            )
            return {
                "distance_km": route.get("distance_km", 0),
                "duration_minutes": route.get("duration_minutes", 0),
                "steps": route.get("steps", []),
            }
        except NotImplementedError:
            return {"error": "Route calculation not supported by geolocation provider"}
        except Exception as e:
            return {"error": str(e)}

    return [get_vehicle_position, get_fleet_overview, get_vehicle_history, check_geofence_violations, calculate_route]
