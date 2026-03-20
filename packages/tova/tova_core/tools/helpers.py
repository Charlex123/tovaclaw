"""Proximity and utility helpers for tools."""

import math
from datetime import datetime, timezone


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def filter_by_radius(items: list, lat: float, lon: float, radius_km: float) -> list:
    """Filter items that have lat/lon within radius_km of the user."""
    if not radius_km or radius_km <= 0:
        return items
    filtered = []
    for item in items:
        item_lat = item.get("latitude") or item.get("lat")
        item_lon = item.get("longitude") or item.get("lon") or item.get("lng")
        if item_lat and item_lon:
            dist = distance_km(lat, lon, float(item_lat), float(item_lon))
            item["distance_km"] = round(dist, 1)
            if dist <= radius_km:
                filtered.append(item)
        else:
            filtered.append(item)
    return filtered


EXPANSION_RADII = [5, 10, 20, 35, 50]


def suggest_next_radius(current_radius: float) -> float | None:
    """Suggest the next expansion radius, or None if maxed out."""
    for r in EXPANSION_RADII:
        if r > current_radius:
            return r
    return None


def is_future_date(date_val) -> bool:
    """Return True if the date value represents today or a future date."""
    if date_val is None:
        return False
    now = datetime.now(timezone.utc)
    if isinstance(date_val, datetime):
        if date_val.tzinfo is None:
            date_val = date_val.replace(tzinfo=timezone.utc)
        return date_val >= now
    if isinstance(date_val, dict) and "_seconds" in date_val:
        return datetime.fromtimestamp(date_val["_seconds"], tz=timezone.utc) >= now
    if isinstance(date_val, str):
        try:
            parsed = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            return parsed >= now
        except (ValueError, TypeError):
            return False
    return False


def safe_timestamp(value) -> str:
    """Convert various timestamp formats to a string."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("_seconds", ""))
    if isinstance(value, str):
        return value
    return str(value)
