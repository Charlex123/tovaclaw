"""
Flight search provider — searches real flight data via SerpAPI Google Flights
or falls back to Amadeus API, or a local airport/airline knowledge base.

No payment. No booking execution. Tova finds flights, compares prices,
and gives the user a direct link to book on the airline's site.

Supported backends (in priority order):
    1. SerpAPI Google Flights (SERPAPI_API_KEY) — real-time Google Flights data
    2. Amadeus Self-Service API (AMADEUS_API_KEY + AMADEUS_API_SECRET) — GDS data
    3. Built-in knowledge base — offline IATA codes + airline info, no live prices

Usage:
    provider = FlightSearchProvider()
    results = await provider.search_flights("Lagos", "Port Harcourt", "2026-03-30")
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

from tova_core.providers.travel import BaseTravelProvider

logger = logging.getLogger(__name__)


# ── Built-in IATA Airport Database ──────────────────────────────────
# Common airports — enough for the agent to resolve city names without an API call.

AIRPORT_DB: dict[str, dict[str, Any]] = {
    # Nigeria
    "LOS": {"city": "Lagos", "name": "Murtala Muhammed International", "country": "Nigeria"},
    "ABV": {"city": "Abuja", "name": "Nnamdi Azikiwe International", "country": "Nigeria"},
    "PHC": {"city": "Port Harcourt", "name": "Port Harcourt International", "country": "Nigeria"},
    "ENU": {"city": "Enugu", "name": "Akanu Ibiam International", "country": "Nigeria"},
    "KAN": {"city": "Kano", "name": "Mallam Aminu Kano International", "country": "Nigeria"},
    "BNI": {"city": "Benin City", "name": "Benin Airport", "country": "Nigeria"},
    "CBQ": {"city": "Calabar", "name": "Margaret Ekpo International", "country": "Nigeria"},
    "QOW": {"city": "Owerri", "name": "Sam Mbakwe International", "country": "Nigeria"},
    "ILR": {"city": "Ilorin", "name": "Ilorin International", "country": "Nigeria"},
    "AKR": {"city": "Akure", "name": "Akure Airport", "country": "Nigeria"},
    "QRW": {"city": "Warri", "name": "Osubi Airstrip", "country": "Nigeria"},
    "JOS": {"city": "Jos", "name": "Yakubu Gowon Airport", "country": "Nigeria"},
    "MDI": {"city": "Makurdi", "name": "Makurdi Airport", "country": "Nigeria"},
    "ASK": {"city": "Asaba", "name": "Asaba International", "country": "Nigeria"},
    "KAD": {"city": "Kaduna", "name": "Kaduna Airport", "country": "Nigeria"},
    # West Africa
    "ACC": {"city": "Accra", "name": "Kotoka International", "country": "Ghana"},
    "DSS": {"city": "Dakar", "name": "Blaise Diagne International", "country": "Senegal"},
    "ABJ": {"city": "Abidjan", "name": "Felix Houphouet-Boigny", "country": "Ivory Coast"},
    # East Africa
    "NBO": {"city": "Nairobi", "name": "Jomo Kenyatta International", "country": "Kenya"},
    "ADD": {"city": "Addis Ababa", "name": "Bole International", "country": "Ethiopia"},
    "DAR": {"city": "Dar es Salaam", "name": "Julius Nyerere International", "country": "Tanzania"},
    "EBB": {"city": "Entebbe", "name": "Entebbe International", "country": "Uganda"},
    # Southern Africa
    "JNB": {"city": "Johannesburg", "name": "O.R. Tambo International", "country": "South Africa"},
    "CPT": {"city": "Cape Town", "name": "Cape Town International", "country": "South Africa"},
    # North Africa / Middle East
    "CAI": {"city": "Cairo", "name": "Cairo International", "country": "Egypt"},
    "DXB": {"city": "Dubai", "name": "Dubai International", "country": "UAE"},
    "AUH": {"city": "Abu Dhabi", "name": "Zayed International", "country": "UAE"},
    "DOH": {"city": "Doha", "name": "Hamad International", "country": "Qatar"},
    "JED": {"city": "Jeddah", "name": "King Abdulaziz International", "country": "Saudi Arabia"},
    # Europe
    "LHR": {"city": "London", "name": "Heathrow", "country": "United Kingdom"},
    "LGW": {"city": "London", "name": "Gatwick", "country": "United Kingdom"},
    "CDG": {"city": "Paris", "name": "Charles de Gaulle", "country": "France"},
    "AMS": {"city": "Amsterdam", "name": "Schiphol", "country": "Netherlands"},
    "FRA": {"city": "Frankfurt", "name": "Frankfurt Airport", "country": "Germany"},
    "IST": {"city": "Istanbul", "name": "Istanbul Airport", "country": "Turkey"},
    # Americas
    "JFK": {"city": "New York", "name": "John F. Kennedy International", "country": "USA"},
    "LAX": {"city": "Los Angeles", "name": "Los Angeles International", "country": "USA"},
    "ATL": {"city": "Atlanta", "name": "Hartsfield-Jackson", "country": "USA"},
    "ORD": {"city": "Chicago", "name": "O'Hare International", "country": "USA"},
    "IAH": {"city": "Houston", "name": "George Bush Intercontinental", "country": "USA"},
    "GRU": {"city": "Sao Paulo", "name": "Guarulhos International", "country": "Brazil"},
    "YYZ": {"city": "Toronto", "name": "Pearson International", "country": "Canada"},
    # Asia
    "SIN": {"city": "Singapore", "name": "Changi Airport", "country": "Singapore"},
    "HKG": {"city": "Hong Kong", "name": "Hong Kong International", "country": "Hong Kong"},
    "PEK": {"city": "Beijing", "name": "Capital International", "country": "China"},
    "DEL": {"city": "Delhi", "name": "Indira Gandhi International", "country": "India"},
    "BOM": {"city": "Mumbai", "name": "Chhatrapati Shivaji Maharaj", "country": "India"},
}

# City name → IATA code reverse lookup
_CITY_TO_IATA: dict[str, str] = {}
for _code, _info in AIRPORT_DB.items():
    _city = _info["city"].lower()
    if _city not in _CITY_TO_IATA:
        _CITY_TO_IATA[_city] = _code
    # Also index common aliases
    if _city == "port harcourt":
        _CITY_TO_IATA["portharcourt"] = _code
        _CITY_TO_IATA["ph"] = _code
        _CITY_TO_IATA["pharcourt"] = _code
    elif _city == "abuja":
        _CITY_TO_IATA["fct"] = _code
    elif _city == "lagos":
        _CITY_TO_IATA["ikeja"] = _code
    elif _city == "new york":
        _CITY_TO_IATA["nyc"] = _code
    elif _city == "london":
        _CITY_TO_IATA["lon"] = _code
    elif _city == "sao paulo":
        _CITY_TO_IATA["são paulo"] = _code
        _CITY_TO_IATA["saopaulo"] = _code
    elif _city == "dar es salaam":
        _CITY_TO_IATA["dar"] = _code


# ── Nigerian Airlines Database ────────────────────────────────────
NIGERIAN_AIRLINES = {
    "air_peace": {
        "name": "Air Peace",
        "code": "P4",
        "logo": "https://www.airpeace.com/images/logo.png",
        "booking_url": "https://www.airpeace.com",
        "domestic": True,
        "international": True,
    },
    "ibom_air": {
        "name": "Ibom Air",
        "code": "QI",
        "logo": "https://www.ibomair.com/images/logo.png",
        "booking_url": "https://www.ibomair.com",
        "domestic": True,
        "international": False,
    },
    "united_nigeria": {
        "name": "United Nigeria Airlines",
        "code": "UM",
        "booking_url": "https://www.flyunitednigeria.com",
        "domestic": True,
        "international": False,
    },
    "green_africa": {
        "name": "Green Africa Airways",
        "code": "Q9",
        "booking_url": "https://www.greenafrica.com",
        "domestic": True,
        "international": False,
    },
    "valuejet": {
        "name": "ValueJet",
        "code": "VJ",
        "booking_url": "https://www.valuejetair.com",
        "domestic": True,
        "international": False,
    },
    "max_air": {
        "name": "Max Air",
        "code": "VM",
        "booking_url": "https://www.maxair.com.ng",
        "domestic": True,
        "international": True,
    },
    "overland": {
        "name": "Overland Airways",
        "code": "OF",
        "booking_url": "https://www.overlandairways.com",
        "domestic": True,
        "international": False,
    },
}



# ── Airport coordinates for proximity search ──────────────────────
# Lat/lon for airports — used to find the nearest departure airport
# to the user's GPS location.

AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    # Nigeria
    "LOS": (6.5774, 3.3213), "ABV": (9.0068, 7.2632), "PHC": (5.0155, 6.9496),
    "ENU": (6.4743, 7.5620), "KAN": (12.0476, 8.5246), "BNI": (6.3165, 5.5999),
    "CBQ": (4.9762, 8.3470), "QOW": (5.4271, 7.2064), "ILR": (8.4401, 4.4940),
    "AKR": (7.2466, 5.3010), "JOS": (9.6398, 8.8691), "ASK": (6.2041, 6.6653),
    "KAD": (10.6960, 7.3201),
    # West Africa
    "ACC": (5.6052, -0.1668), "DSS": (14.6700, -17.0730), "ABJ": (5.2614, -3.9262),
    # East Africa
    "NBO": (-1.3192, 36.9278), "ADD": (8.9779, 38.7993), "DAR": (-6.8781, 39.2026),
    "EBB": (0.0424, 32.4435),
    # Southern Africa
    "JNB": (-26.1392, 28.2460), "CPT": (-33.9649, 18.6017),
    # North Africa / Middle East
    "CAI": (30.1219, 31.4056), "DXB": (25.2528, 55.3644), "AUH": (24.4330, 54.6511),
    "DOH": (25.2609, 51.6138), "JED": (21.6796, 39.1566),
    # Europe
    "LHR": (51.4700, -0.4543), "LGW": (51.1537, -0.1821), "CDG": (49.0097, 2.5479),
    "AMS": (52.3105, 4.7683), "FRA": (50.0379, 8.5622), "IST": (41.2608, 28.7419),
    # Americas
    "JFK": (40.6413, -73.7781), "LAX": (33.9416, -118.4085), "ATL": (33.6407, -84.4277),
    "ORD": (41.9742, -87.9073), "IAH": (29.9844, -95.3414), "GRU": (-23.4356, -46.4731),
    "YYZ": (43.6777, -79.6248),
    # Asia
    "SIN": (1.3644, 103.9915), "HKG": (22.3080, 113.9185), "PEK": (40.0799, 116.6031),
    "DEL": (28.5562, 77.1000), "BOM": (19.0896, 72.8656),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two lat/lon points."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_airports(lat: float, lon: float, limit: int = 3, max_km: float = 500) -> list[dict]:
    """Find the nearest airports to a GPS coordinate.

    Args:
        lat: User's latitude
        lon: User's longitude
        limit: Max airports to return
        max_km: Maximum distance to consider

    Returns:
        List of dicts with code, city, distance_km, sorted by proximity
    """
    distances = []
    for code, (a_lat, a_lon) in AIRPORT_COORDS.items():
        dist = _haversine_km(lat, lon, a_lat, a_lon)
        if dist <= max_km:
            info = AIRPORT_DB.get(code, {})
            distances.append({
                "code": code,
                "city": info.get("city", ""),
                "name": info.get("name", ""),
                "country": info.get("country", ""),
                "distance_km": round(dist, 1),
            })
    distances.sort(key=lambda x: x["distance_km"])
    return distances[:limit]


def _resolve_airport(query: str) -> dict:
    """Resolve a city name or code to airport info."""
    q = query.strip().upper()
    # Direct IATA code
    if q in AIRPORT_DB:
        return {"code": q, **AIRPORT_DB[q]}

    # City name lookup
    q_lower = query.strip().lower().replace("-", " ").replace("_", " ")
    # Remove common suffixes
    for suffix in [" airport", " intl", " international"]:
        q_lower = q_lower.replace(suffix, "")
    q_lower = q_lower.strip()

    if q_lower in _CITY_TO_IATA:
        code = _CITY_TO_IATA[q_lower]
        return {"code": code, **AIRPORT_DB[code]}

    # Fuzzy: check if query is substring of any city
    matches = []
    for code, info in AIRPORT_DB.items():
        city_lower = info["city"].lower()
        if q_lower in city_lower or city_lower in q_lower:
            matches.append({"code": code, **info})
    if matches:
        return matches[0]

    return {"code": "", "city": query, "name": "Unknown", "country": "Unknown"}


class FlightSearchProvider(BaseTravelProvider):
    """Multi-backend flight search provider.

    Priority:
        1. SerpAPI Google Flights (real-time, easy setup)
        2. Amadeus API (GDS, requires registration)
        3. Offline mode (airport info only, no prices)
    """

    def __init__(self):
        self.serpapi_key = os.environ.get("SERPAPI_API_KEY", "")
        self.amadeus_key = os.environ.get("AMADEUS_API_KEY", "")
        self.amadeus_secret = os.environ.get("AMADEUS_API_SECRET", "")
        self._amadeus_token: str = ""
        self._amadeus_token_expiry: float = 0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def find_nearest_airports(
        self,
        latitude: float,
        longitude: float,
        limit: int = 3,
        max_km: float = 500,
    ) -> list[dict]:
        """Find nearest airports to user's GPS coordinates."""
        return find_nearest_airports(latitude, longitude, limit, max_km)

    async def get_airport_code(self, city_or_query: str) -> dict:
        """Resolve city name to IATA airport code."""
        result = _resolve_airport(city_or_query)
        if result["code"]:
            return {
                "code": result["code"],
                "city": result["city"],
                "airport_name": result["name"],
                "country": result["country"],
            }
        return {
            "code": "",
            "city": city_or_query,
            "airport_name": "Not found",
            "country": "",
            "suggestion": (
                "Could not find an airport for this city. "
                "Try using the IATA airport code directly (e.g., LOS, PHC, ABV)."
            ),
        }

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = "",
        adults: int = 1,
        children: int = 0,
        cabin_class: str = "economy",
        max_results: int = 10,
        sort_by: str = "price",
        time_preference: str = "",
    ) -> dict:
        """Search flights using the best available backend."""
        # Resolve city names to IATA codes
        origin_info = _resolve_airport(origin)
        dest_info = _resolve_airport(destination)

        origin_code = origin_info.get("code", origin.upper()[:3])
        dest_code = dest_info.get("code", destination.upper()[:3])

        metadata = {
            "origin": {"code": origin_code, "city": origin_info.get("city", origin)},
            "destination": {"code": dest_code, "city": dest_info.get("city", destination)},
            "departure_date": departure_date,
            "return_date": return_date,
            "passengers": {"adults": adults, "children": children},
            "cabin_class": cabin_class,
            "time_preference": time_preference,
        }

        # Try SerpAPI first
        if self.serpapi_key:
            try:
                flights = await self._search_serpapi(
                    origin_code, dest_code, departure_date,
                    return_date, adults, cabin_class, time_preference,
                )
                if flights:
                    if sort_by == "price":
                        flights.sort(key=lambda f: f.get("price", float("inf")))
                    elif sort_by == "duration":
                        flights.sort(key=lambda f: f.get("duration_minutes", float("inf")))
                    elif sort_by == "departure_time":
                        flights.sort(key=lambda f: f.get("departure_time", ""))

                    return {
                        "flights": flights[:max_results],
                        "total_found": len(flights),
                        "source": "google_flights",
                        "search_metadata": metadata,
                    }
            except Exception as e:
                logger.warning(f"SerpAPI flight search failed: {e}")

        # Try Amadeus
        if self.amadeus_key and self.amadeus_secret:
            try:
                flights = await self._search_amadeus(
                    origin_code, dest_code, departure_date,
                    return_date, adults, children, cabin_class, time_preference,
                )
                if flights:
                    if sort_by == "price":
                        flights.sort(key=lambda f: f.get("price", float("inf")))
                    elif sort_by == "duration":
                        flights.sort(key=lambda f: f.get("duration_minutes", float("inf")))
                    elif sort_by == "departure_time":
                        flights.sort(key=lambda f: f.get("departure_time", ""))

                    return {
                        "flights": flights[:max_results],
                        "total_found": len(flights),
                        "source": "amadeus",
                        "search_metadata": metadata,
                    }
            except Exception as e:
                logger.warning(f"Amadeus flight search failed: {e}")

        # Offline fallback — return airline directory for manual search
        return self._offline_fallback(origin_code, dest_code, metadata)

    # ── SerpAPI Google Flights ───────────────────────────────────

    async def _search_serpapi(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        adults: int,
        cabin_class: str,
        time_preference: str,
    ) -> list[dict]:
        """Search via SerpAPI Google Flights endpoint."""
        client = await self._get_client()

        cabin_map = {
            "economy": 1, "premium_economy": 2,
            "business": 3, "first": 4,
        }

        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": departure_date,
            "type": "2" if not return_date else "1",  # 1=round, 2=one-way
            "adults": str(adults),
            "travel_class": str(cabin_map.get(cabin_class, 1)),
            "currency": "NGN",
            "hl": "en",
            "api_key": self.serpapi_key,
        }
        if return_date:
            params["return_date"] = return_date

        resp = await client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        data = resp.json()

        flights = []

        # Parse "best_flights" and "other_flights"
        for group_key in ("best_flights", "other_flights"):
            for offer in data.get(group_key, []):
                legs = offer.get("flights", [])
                if not legs:
                    continue

                first_leg = legs[0]
                last_leg = legs[-1]

                airline = first_leg.get("airline", "")
                flight_no = first_leg.get("flight_number", "")
                dep_time = first_leg.get("departure_airport", {}).get("time", "")
                arr_time = last_leg.get("arrival_airport", {}).get("time", "")
                duration = offer.get("total_duration", 0)
                stops = len(legs) - 1

                price = offer.get("price", 0)

                # Time preference filter
                if time_preference and dep_time:
                    hour = int(dep_time.split(":")[0]) if ":" in dep_time else 12
                    if time_preference == "morning" and hour >= 12:
                        continue
                    elif time_preference == "afternoon" and (hour < 12 or hour >= 17):
                        continue
                    elif time_preference == "evening" and hour < 17:
                        continue

                # Build booking URL from airline
                airline_lower = airline.lower().replace(" ", "_")
                booking_url = ""
                for ak, av in NIGERIAN_AIRLINES.items():
                    if av["name"].lower() in airline.lower() or av.get("code", "") == flight_no[:2]:
                        booking_url = av["booking_url"]
                        break
                if not booking_url:
                    booking_url = f"https://www.google.com/travel/flights?q=flights+{origin}+to+{destination}+{departure_date}"

                layover_info = ""
                if stops > 0:
                    layover_airports = [
                        leg.get("arrival_airport", {}).get("id", "")
                        for leg in legs[:-1]
                    ]
                    layover_info = ", ".join(filter(None, layover_airports))

                flights.append({
                    "id": f"{flight_no}_{departure_date}",
                    "airline": airline,
                    "flight_number": flight_no,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "duration_minutes": duration,
                    "duration_display": f"{duration // 60}h {duration % 60}m" if duration else "",
                    "stops": stops,
                    "stop_details": layover_info,
                    "price": price,
                    "currency": "NGN",
                    "cabin_class": cabin_class,
                    "booking_url": booking_url,
                    "is_best": group_key == "best_flights",
                })

        return flights

    # ── Amadeus API ──────────────────────────────────────────────

    async def _get_amadeus_token(self) -> str:
        """Get or refresh Amadeus OAuth2 token."""
        import time
        if self._amadeus_token and time.time() < self._amadeus_token_expiry:
            return self._amadeus_token

        client = await self._get_client()
        resp = await client.post(
            "https://api.amadeus.com/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.amadeus_key,
                "client_secret": self.amadeus_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._amadeus_token = data["access_token"]
        self._amadeus_token_expiry = time.time() + data.get("expires_in", 1799) - 60
        return self._amadeus_token

    async def _search_amadeus(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        adults: int,
        children: int,
        cabin_class: str,
        time_preference: str,
    ) -> list[dict]:
        """Search via Amadeus Flight Offers Search API."""
        token = await self._get_amadeus_token()
        client = await self._get_client()

        cabin_map = {
            "economy": "ECONOMY", "premium_economy": "PREMIUM_ECONOMY",
            "business": "BUSINESS", "first": "FIRST",
        }

        params: dict[str, Any] = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "travelClass": cabin_map.get(cabin_class, "ECONOMY"),
            "currencyCode": "NGN",
            "max": 20,
        }
        if return_date:
            params["returnDate"] = return_date
        if children:
            params["children"] = children

        resp = await client.get(
            "https://api.amadeus.com/v2/shopping/flight-offers",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()

        # Airline dictionary from response
        carriers = data.get("dictionaries", {}).get("carriers", {})

        flights = []
        for offer in data.get("data", []):
            price_info = offer.get("price", {})
            price = float(price_info.get("grandTotal", 0))

            for itin in offer.get("itineraries", []):
                segments = itin.get("segments", [])
                if not segments:
                    continue

                first_seg = segments[0]
                last_seg = segments[-1]

                carrier_code = first_seg.get("carrierCode", "")
                airline = carriers.get(carrier_code, carrier_code)
                flight_no = f"{carrier_code}{first_seg.get('number', '')}"

                dep_time = first_seg.get("departure", {}).get("at", "")
                arr_time = last_seg.get("arrival", {}).get("at", "")

                # Parse duration (PT2H30M → 150)
                raw_duration = itin.get("duration", "")
                duration_minutes = _parse_iso_duration(raw_duration)

                stops = len(segments) - 1

                # Time filter
                if time_preference and dep_time:
                    hour = int(dep_time[11:13]) if len(dep_time) > 13 else 12
                    if time_preference == "morning" and hour >= 12:
                        continue
                    elif time_preference == "afternoon" and (hour < 12 or hour >= 17):
                        continue
                    elif time_preference == "evening" and hour < 17:
                        continue

                booking_url = ""
                for ak, av in NIGERIAN_AIRLINES.items():
                    if av.get("code") == carrier_code:
                        booking_url = av["booking_url"]
                        break
                if not booking_url:
                    booking_url = f"https://www.google.com/travel/flights?q=flights+{origin}+to+{destination}+{departure_date}"

                flights.append({
                    "id": offer.get("id", f"{flight_no}_{departure_date}"),
                    "airline": airline,
                    "flight_number": flight_no,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "duration_minutes": duration_minutes,
                    "duration_display": f"{duration_minutes // 60}h {duration_minutes % 60}m",
                    "stops": stops,
                    "price": price,
                    "currency": price_info.get("currency", "NGN"),
                    "cabin_class": cabin_class,
                    "booking_url": booking_url,
                    "is_best": False,
                })

        return flights

    # ── Offline Fallback ─────────────────────────────────────────

    def _offline_fallback(self, origin: str, dest: str, metadata: dict) -> dict:
        """No API key configured — return airline directory for manual search."""
        origin_info = AIRPORT_DB.get(origin, {})
        dest_info = AIRPORT_DB.get(dest, {})

        is_domestic_ng = (
            origin_info.get("country") == "Nigeria"
            and dest_info.get("country") == "Nigeria"
        )

        airlines = []
        for key, info in NIGERIAN_AIRLINES.items():
            if is_domestic_ng and info.get("domestic"):
                airlines.append({
                    "name": info["name"],
                    "booking_url": info["booking_url"],
                    "type": "domestic",
                })
            elif not is_domestic_ng and info.get("international"):
                airlines.append({
                    "name": info["name"],
                    "booking_url": info["booking_url"],
                    "type": "international",
                })

        if not is_domestic_ng:
            airlines.extend([
                {"name": "Ethiopian Airlines", "booking_url": "https://www.ethiopianairlines.com", "type": "international"},
                {"name": "Emirates", "booking_url": "https://www.emirates.com", "type": "international"},
                {"name": "Qatar Airways", "booking_url": "https://www.qatarairways.com", "type": "international"},
                {"name": "British Airways", "booking_url": "https://www.britishairways.com", "type": "international"},
                {"name": "Turkish Airlines", "booking_url": "https://www.turkishairlines.com", "type": "international"},
            ])

        google_flights_url = (
            f"https://www.google.com/travel/flights?q=flights+"
            f"{origin}+to+{dest}+{metadata.get('search_metadata', metadata).get('departure_date', '')}"
        )

        return {
            "flights": [],
            "total_found": 0,
            "source": "offline",
            "search_metadata": metadata,
            "note": (
                "No flight search API configured. Set SERPAPI_API_KEY or "
                "AMADEUS_API_KEY + AMADEUS_API_SECRET for live flight prices."
            ),
            "airlines": airlines,
            "manual_search_urls": {
                "google_flights": google_flights_url,
                "wakanow": f"https://www.wakanow.com/flights",
                "travelbeta": f"https://www.travelbeta.com",
                "kiwi": f"https://www.kiwi.com/en/search/results/{origin}/{dest}/{metadata.get('search_metadata', metadata).get('departure_date', '')}",
            },
            "guidance": (
                "No live price data available. Show the airlines that fly this route "
                "and the manual search URLs. Do NOT quote any prices — tell the user "
                "to check the links for current fares. Never guess or estimate prices."
            ),
        }

    # ── Train Search ────────────────────────────────────────────

    async def search_trains(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = "",
        passengers: int = 1,
        train_class: str = "standard",
        max_results: int = 10,
        sort_by: str = "price",
        time_preference: str = "",
    ) -> dict:
        """Search for train routes using available backends."""
        origin_station = _resolve_train_station(origin)
        dest_station = _resolve_train_station(destination)

        metadata = {
            "origin": origin_station,
            "destination": dest_station,
            "departure_date": departure_date,
            "return_date": return_date,
            "passengers": passengers,
            "train_class": train_class,
            "time_preference": time_preference,
        }

        # Search the web for current train prices and schedules
        if self.serpapi_key:
            try:
                web_results = await self._search_trains_serpapi(
                    origin_station.get("city", origin),
                    dest_station.get("city", destination),
                    departure_date, time_preference,
                )
                if web_results:
                    # Get offline route/operator info to combine with live web data
                    offline = self._train_offline_fallback(origin_station, dest_station, metadata)
                    offline["source"] = "web_search"
                    offline["web_results"] = web_results
                    offline["guidance"] = (
                        "I searched the web for current train prices. Use the web_results "
                        "snippets to find CURRENT prices — do NOT make up prices. "
                        "If the snippets contain prices, quote them with the source. "
                        "If no prices found in snippets, tell the user to check the booking URL directly."
                    )
                    return offline
            except Exception as e:
                logger.warning(f"SerpAPI train search failed: {e}")

        # Offline fallback — train operator directory
        return self._train_offline_fallback(origin_station, dest_station, metadata)

    async def _search_web_transport(
        self,
        query: str,
    ) -> list[dict]:
        """Search the web for transport info via SerpAPI Google Search.

        Returns organic search results with titles, snippets, and links
        so the LLM can extract current prices and schedules from real web data.
        """
        client = await self._get_client()
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "num": 8,
            "gl": "ng",  # Prioritize Nigerian results
        }
        resp = await client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "source": item.get("displayed_link", ""),
            })

        # Also grab answer box if present (often has prices)
        answer_box = data.get("answer_box")
        if answer_box:
            results.insert(0, {
                "title": answer_box.get("title", "Featured Answer"),
                "snippet": answer_box.get("snippet", answer_box.get("answer", "")),
                "link": answer_box.get("link", ""),
                "source": "Google Answer Box",
            })

        return results

    async def _search_trains_serpapi(
        self,
        origin_city: str,
        dest_city: str,
        departure_date: str,
        time_preference: str,
    ) -> list[dict]:
        """Search for trains via SerpAPI — returns web results with real prices."""
        results = await self._search_web_transport(
            f"train {origin_city} to {dest_city} {departure_date} schedule price ticket booking"
        )
        # Return as web_results for the LLM to parse — we don't fabricate prices
        return results  # These are web snippets, not structured train data

    def _train_offline_fallback(
        self, origin: dict, dest: dict, metadata: dict,
    ) -> dict:
        """Return train operator directory for manual booking."""
        origin_country = origin.get("country", "")
        dest_country = dest.get("country", "")
        origin_city = origin.get("city", "")
        dest_city = dest.get("city", "")

        operators = []
        route_available = False

        # Check if route exists in known routes
        route_key = f"{origin_city.lower()}_{dest_city.lower()}"
        reverse_key = f"{dest_city.lower()}_{origin_city.lower()}"
        for rk in (route_key, reverse_key):
            if rk in TRAIN_ROUTES:
                route_info = TRAIN_ROUTES[rk]
                route_available = True
                operators.append({
                    "name": route_info["operator"],
                    "route": route_info["route_name"],
                    "duration": route_info.get("duration", ""),
                    "booking_url": route_info.get("booking_url", ""),
                    "schedule_note": route_info.get("schedule_note", ""),
                    "price_note": route_info.get("price_note", "Check operator website for current fares"),
                })

        # Add general operators for the country
        if origin_country == "Nigeria" or dest_country == "Nigeria":
            for op in TRAIN_OPERATORS_NG:
                operators.append(op)
        elif origin_country == "United Kingdom" or dest_country == "United Kingdom":
            for op in TRAIN_OPERATORS_UK:
                operators.append(op)
        else:
            for op in TRAIN_OPERATORS_INTL:
                operators.append(op)

        return {
            "trains": [],
            "total_found": 0,
            "source": "offline",
            "route_available": route_available,
            "search_metadata": metadata,
            "operators": operators,
            "guidance": (
                f"Train route {'found' if route_available else 'not confirmed'} for "
                f"{origin_city} → {dest_city}. "
                "Here are the train operators for this region — check their sites for schedules and prices."
            ),
        }

    async def get_train_station(self, city_or_query: str) -> dict:
        return _resolve_train_station(city_or_query)

    async def find_nearest_stations(
        self,
        latitude: float,
        longitude: float,
        limit: int = 3,
        max_km: float = 200,
    ) -> list[dict]:
        """Find nearest train stations to GPS coordinates."""
        results = []
        for name, info in TRAIN_STATION_DB.items():
            coords = info.get("coords")
            if not coords:
                continue
            dist = _haversine_km(latitude, longitude, coords[0], coords[1])
            if dist <= max_km:
                results.append({
                    "station": name,
                    "city": info.get("city", ""),
                    "country": info.get("country", ""),
                    "distance_km": round(dist, 1),
                })
        results.sort(key=lambda x: x["distance_km"])
        return results[:limit]

    # ── Bus / Road Transport Search ──────────────────────────────

    async def search_buses(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = "",
        passengers: int = 1,
        max_results: int = 10,
        sort_by: str = "price",
        time_preference: str = "",
    ) -> dict:
        """Search for intercity bus routes."""
        metadata = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "passengers": passengers,
            "time_preference": time_preference,
        }

        # Search the web for current bus prices first
        web_results = []
        if self.serpapi_key:
            try:
                web_results = await self._search_web_transport(
                    f"bus {origin} to {destination} {departure_date} price ticket booking GIGM ABC transport"
                )
            except Exception as e:
                logger.warning(f"SerpAPI bus search failed: {e}")

        # Resolve cities
        origin_lower = origin.strip().lower()
        dest_lower = destination.strip().lower()

        # Check known routes
        route_key = f"{origin_lower}_{dest_lower}"
        reverse_key = f"{dest_lower}_{origin_lower}"

        route_info = BUS_ROUTES.get(route_key) or BUS_ROUTES.get(reverse_key)

        operators = []
        # Find operators that serve these cities
        for op_key, op_info in BUS_OPERATORS.items():
            cities_served = [c.lower() for c in op_info.get("cities", [])]
            if origin_lower in cities_served or dest_lower in cities_served:
                operators.append({
                    "name": op_info["name"],
                    "booking_url": op_info["booking_url"],
                    "phone": op_info.get("phone", ""),
                    "type": op_info.get("type", "standard"),
                    "serves_route": (origin_lower in cities_served and dest_lower in cities_served),
                })

        # If no specific operators found, return all for the country
        if not operators:
            # Guess country from airport DB
            origin_airport = _resolve_airport(origin)
            country = origin_airport.get("country", "")
            if country == "Nigeria":
                operators = [
                    {"name": v["name"], "booking_url": v["booking_url"],
                     "phone": v.get("phone", ""), "type": v.get("type", "standard"),
                     "serves_route": False}
                    for v in BUS_OPERATORS.values()
                    if v.get("country") == "Nigeria"
                ]

        return {
            "buses": [],
            "total_found": 0,
            "source": "web_search" if web_results else "offline",
            "route_info": route_info,
            "operators": operators,
            "web_results": web_results,
            "search_metadata": metadata,
            "guidance": (
                "I searched the web for current bus prices. Use the web_results "
                "snippets to find CURRENT prices — do NOT make up or guess prices. "
                "If the snippets contain prices, quote them with the source URL. "
                "If no prices found in snippets, tell the user to check the operator's "
                "website or call them for current fares. "
                f"Operators on the {origin} → {destination} route are listed."
            ) if web_results else (
                "No live price data available. Show the user the operators that serve "
                f"the {origin} → {destination} route and their booking URLs. "
                "Do NOT quote any prices — tell them to check the websites for current fares."
            ),
        }

    async def search_car_hire(
        self,
        pickup_location: str,
        dropoff_location: str = "",
        pickup_date: str = "",
        dropoff_date: str = "",
        car_type: str = "any",
        max_results: int = 10,
        sort_by: str = "price",
    ) -> dict:
        """Search for car hire / rental options."""
        metadata = {
            "pickup_location": pickup_location,
            "dropoff_location": dropoff_location or pickup_location,
            "pickup_date": pickup_date,
            "dropoff_date": dropoff_date or pickup_date,
            "car_type": car_type,
        }

        # Resolve location
        location_airport = _resolve_airport(pickup_location)
        country = location_airport.get("country", "")

        providers = []
        for provider_key, provider_info in CAR_HIRE_PROVIDERS.items():
            if provider_info.get("country") == country or provider_info.get("international"):
                providers.append({
                    "name": provider_info["name"],
                    "booking_url": provider_info["booking_url"],
                    "phone": provider_info.get("phone", ""),
                    "car_types": provider_info.get("car_types", []),
                    "note": provider_info.get("note", "Check website for current prices"),
                })

        return {
            "cars": [],
            "total_found": 0,
            "source": "offline",
            "providers": providers,
            "search_metadata": metadata,
            "guidance": (
                f"Here are car hire companies available in {pickup_location}. "
                "Contact them or visit their sites to check availability and prices."
            ),
        }

    async def find_nearest_terminals(
        self,
        latitude: float,
        longitude: float,
        transport_type: str = "bus",
        limit: int = 3,
        max_km: float = 100,
    ) -> list[dict]:
        """Find nearest bus terminals to GPS coordinates."""
        db = BUS_TERMINAL_COORDS if transport_type == "bus" else TRAIN_STATION_DB
        results = []
        for name, info in db.items():
            coords = info.get("coords")
            if not coords:
                continue
            dist = _haversine_km(latitude, longitude, coords[0], coords[1])
            if dist <= max_km:
                results.append({
                    "terminal": name,
                    "city": info.get("city", ""),
                    "country": info.get("country", ""),
                    "distance_km": round(dist, 1),
                    "type": transport_type,
                })
        results.sort(key=lambda x: x["distance_km"])
        return results[:limit]

    # ── Multi-Modal Comparison ───────────────────────────────────

    async def compare_transport(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: int = 1,
    ) -> dict:
        """Compare flights, trains, and buses for the same route."""
        import asyncio

        flight_task = self.search_flights(
            origin, destination, departure_date, adults=passengers, max_results=3,
        )
        train_task = self.search_trains(
            origin, destination, departure_date, passengers=passengers, max_results=3,
        )
        bus_task = self.search_buses(
            origin, destination, departure_date, passengers=passengers, max_results=3,
        )

        flights, trains, buses = await asyncio.gather(
            flight_task, train_task, bus_task,
            return_exceptions=True,
        )

        comparison = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "modes": {},
        }

        if isinstance(flights, dict):
            comparison["modes"]["flight"] = {
                "available": bool(flights.get("flights") or flights.get("airlines")),
                "cheapest": min((f["price"] for f in flights.get("flights", []) if f.get("price")), default=None),
                "results_count": flights.get("total_found", 0),
                "data": flights,
            }
        if isinstance(trains, dict):
            comparison["modes"]["train"] = {
                "available": bool(trains.get("trains") or trains.get("operators")),
                "cheapest": min((t["price"] for t in trains.get("trains", []) if t.get("price")), default=None),
                "results_count": trains.get("total_found", 0),
                "data": trains,
            }
        if isinstance(buses, dict):
            comparison["modes"]["bus"] = {
                "available": bool(buses.get("buses") or buses.get("operators")),
                "cheapest": min((b["price"] for b in buses.get("buses", []) if b.get("price")), default=None),
                "results_count": buses.get("total_found", 0),
                "data": buses,
            }

        comparison["guidance"] = (
            "Present a side-by-side comparison of flight vs train vs bus. "
            "Compare price, travel time, convenience, and departure times. "
            "Recommend the best option based on the user's priorities."
        )

        return comparison

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Train Station Database ──────────────────────────────────────────

TRAIN_STATION_DB: dict[str, dict] = {
    # Nigeria (NRC - Nigerian Railway Corporation)
    "Lagos Mobolaji Johnson": {"city": "Lagos", "country": "Nigeria", "coords": (6.4396, 3.3728)},
    "Ibadan Junction": {"city": "Ibadan", "country": "Nigeria", "coords": (7.3878, 3.9470)},
    "Abeokuta": {"city": "Abeokuta", "country": "Nigeria", "coords": (7.1558, 3.3451)},
    "Idu Abuja": {"city": "Abuja", "country": "Nigeria", "coords": (9.0103, 7.3600)},
    "Kaduna": {"city": "Kaduna", "country": "Nigeria", "coords": (10.5222, 7.4383)},
    "Rigasa Kaduna": {"city": "Kaduna", "country": "Nigeria", "coords": (10.5434, 7.3750)},
    "Warri": {"city": "Warri", "country": "Nigeria", "coords": (5.5167, 5.7500)},
    "Benin": {"city": "Benin City", "country": "Nigeria", "coords": (6.3350, 5.6270)},
    "Kano": {"city": "Kano", "country": "Nigeria", "coords": (12.0022, 8.5167)},
    "Port Harcourt": {"city": "Port Harcourt", "country": "Nigeria", "coords": (4.7774, 7.0134)},
    "Enugu": {"city": "Enugu", "country": "Nigeria", "coords": (6.4472, 7.5103)},
    "Jos": {"city": "Jos", "country": "Nigeria", "coords": (9.9167, 8.9000)},
    "Offa": {"city": "Offa", "country": "Nigeria", "coords": (8.1500, 4.7167)},
    "Ilorin": {"city": "Ilorin", "country": "Nigeria", "coords": (8.4799, 4.5418)},
    # UK
    "London Kings Cross": {"city": "London", "country": "United Kingdom", "coords": (51.5320, -0.1240)},
    "London Euston": {"city": "London", "country": "United Kingdom", "coords": (51.5284, -0.1331)},
    "London Paddington": {"city": "London", "country": "United Kingdom", "coords": (51.5154, -0.1755)},
    "Manchester Piccadilly": {"city": "Manchester", "country": "United Kingdom", "coords": (53.4774, -2.2309)},
    "Birmingham New Street": {"city": "Birmingham", "country": "United Kingdom", "coords": (52.4778, -1.8994)},
    "Edinburgh Waverley": {"city": "Edinburgh", "country": "United Kingdom", "coords": (55.9519, -3.1893)},
    # Europe
    "Paris Gare du Nord": {"city": "Paris", "country": "France", "coords": (48.8809, 2.3553)},
    "Amsterdam Centraal": {"city": "Amsterdam", "country": "Netherlands", "coords": (52.3791, 4.9003)},
    "Frankfurt Hbf": {"city": "Frankfurt", "country": "Germany", "coords": (50.1071, 8.6637)},
}

TRAIN_ROUTES: dict[str, dict] = {
    # Nigeria — active routes
    "lagos_ibadan": {
        "operator": "NRC", "route_name": "Lagos–Ibadan Standard Gauge",
        "duration": "2h 10m", "price_note": "Check nrc.gov.ng for current fares",
        "booking_url": "https://nrc.gov.ng", "schedule_note": "Multiple daily departures",
    },
    "abuja_kaduna": {
        "operator": "NRC", "route_name": "Abuja–Kaduna Standard Gauge",
        "duration": "2h 10m", "price_note": "Check nrc.gov.ng for current fares",
        "booking_url": "https://nrc.gov.ng", "schedule_note": "6+ daily departures",
    },
    "lagos_abeokuta": {
        "operator": "NRC", "route_name": "Lagos–Abeokuta Rail",
        "duration": "1h 30m", "price_note": "Check nrc.gov.ng for current fares",
        "booking_url": "https://nrc.gov.ng", "schedule_note": "Check NRC for schedule",
    },
    "warri_itakpe": {
        "operator": "NRC", "route_name": "Warri–Itakpe Central Line",
        "duration": "~6h", "price_note": "Check nrc.gov.ng for current fares",
        "booking_url": "https://nrc.gov.ng", "schedule_note": "Limited service",
    },
    # UK
    "london_manchester": {
        "operator": "Avanti West Coast", "route_name": "London–Manchester",
        "duration": "2h 10m", "price_note": "Check avantiwestcoast.co.uk for current fares",
        "booking_url": "https://www.avantiwestcoast.co.uk",
        "schedule_note": "Every 20 minutes from Euston",
    },
    "london_edinburgh": {
        "operator": "LNER", "route_name": "London–Edinburgh",
        "duration": "4h 20m", "price_note": "Check lner.co.uk for current fares",
        "booking_url": "https://www.lner.co.uk",
        "schedule_note": "Every 30 minutes from Kings Cross",
    },
    "london_paris": {
        "operator": "Eurostar", "route_name": "London–Paris",
        "duration": "2h 15m", "price_note": "Check eurostar.com for current fares",
        "booking_url": "https://www.eurostar.com",
        "schedule_note": "Up to 18 daily departures from St Pancras",
    },
}

TRAIN_OPERATORS_NG = [
    {"name": "Nigerian Railway Corporation (NRC)", "booking_url": "https://nrc.gov.ng",
     "phone": "+234 1 583 0970", "note": "Government rail — Lagos–Ibadan, Abuja–Kaduna lines"},
]

TRAIN_OPERATORS_UK = [
    {"name": "Trainline", "booking_url": "https://www.thetrainline.com",
     "note": "Compare all UK train operators in one place"},
    {"name": "National Rail", "booking_url": "https://www.nationalrail.co.uk",
     "note": "Official UK rail journey planner"},
    {"name": "Avanti West Coast", "booking_url": "https://www.avantiwestcoast.co.uk"},
    {"name": "LNER", "booking_url": "https://www.lner.co.uk"},
    {"name": "Eurostar", "booking_url": "https://www.eurostar.com", "note": "London to Paris/Brussels/Amsterdam"},
]

TRAIN_OPERATORS_INTL = [
    {"name": "Omio", "booking_url": "https://www.omio.com", "note": "Compare trains across Europe"},
    {"name": "Trainline", "booking_url": "https://www.thetrainline.com", "note": "UK and European trains"},
    {"name": "Rail Europe", "booking_url": "https://www.raileurope.com", "note": "European rail passes and tickets"},
]


def _resolve_train_station(query: str) -> dict:
    """Resolve a city name to a train station."""
    q_lower = query.strip().lower().replace("-", " ").replace("_", " ")
    # Direct station match
    for name, info in TRAIN_STATION_DB.items():
        if q_lower == name.lower() or q_lower == info["city"].lower():
            return {"station": name, "city": info["city"], "country": info["country"]}
    # Fuzzy
    for name, info in TRAIN_STATION_DB.items():
        if q_lower in name.lower() or q_lower in info["city"].lower():
            return {"station": name, "city": info["city"], "country": info["country"]}
    return {"station": "", "city": query, "country": ""}


# ── Bus / Road Transport Database ───────────────────────────────────

BUS_OPERATORS: dict[str, dict] = {
    # Nigeria — major intercity operators
    "gods_is_good": {
        "name": "God Is Good Motors (GIGM)",
        "booking_url": "https://gigm.com",
        "phone": "+234 810 176 0000",
        "type": "luxury",
        "country": "Nigeria",
        "cities": ["Lagos", "Abuja", "Benin City", "Asaba", "Onitsha", "Owerri",
                    "Port Harcourt", "Warri", "Enugu", "Aba", "Uyo", "Calabar"],
    },
    "abc_transport": {
        "name": "ABC Transport",
        "booking_url": "https://abctransport.com",
        "phone": "+234 1 270 0343",
        "type": "standard",
        "country": "Nigeria",
        "cities": ["Lagos", "Abuja", "Port Harcourt", "Calabar", "Uyo", "Benin City",
                    "Warri", "Enugu", "Owerri", "Aba"],
    },
    "peace_mass": {
        "name": "Peace Mass Transit",
        "booking_url": "https://peacemasstransit.com",
        "phone": "+234 803 300 0000",
        "type": "budget",
        "country": "Nigeria",
        "cities": ["Lagos", "Abuja", "Enugu", "Owerri", "Onitsha", "Aba",
                    "Umuahia", "Abakaliki", "Nsukka", "Makurdi", "Jos"],
    },
    "chisco": {
        "name": "Chisco Transport",
        "booking_url": "https://chiscotransport.com",
        "phone": "+234 803 310 1111",
        "type": "standard",
        "country": "Nigeria",
        "cities": ["Lagos", "Abuja", "Owerri", "Port Harcourt", "Onitsha",
                    "Benin City", "Asaba", "Warri"],
    },
    "young_shall_grow": {
        "name": "Young Shall Grow Motors",
        "booking_url": "https://youngshallgrowmotors.com",
        "phone": "+234 803 470 4707",
        "type": "standard",
        "country": "Nigeria",
        "cities": ["Lagos", "Abuja", "Benin City", "Onitsha", "Owerri",
                    "Port Harcourt", "Enugu", "Warri"],
    },
    "libra_motors": {
        "name": "Libra Motors",
        "booking_url": "https://libramotors.com",
        "type": "standard",
        "country": "Nigeria",
        "cities": ["Lagos", "Abuja", "Benin City", "Asaba", "Warri"],
    },
    "cross_country": {
        "name": "Cross Country Transport",
        "booking_url": "https://crosscountrytransport.com",
        "type": "standard",
        "country": "Nigeria",
        "cities": ["Lagos", "Abuja", "Benin City", "Owerri", "Port Harcourt",
                    "Onitsha", "Enugu"],
    },
    "brt_lagos": {
        "name": "BRT Lagos (Bus Rapid Transit)",
        "booking_url": "https://lamata.lagosstate.gov.ng",
        "type": "city_transit",
        "country": "Nigeria",
        "cities": ["Lagos"],
        "note": "Intra-city Lagos only — Ikorodu, Berger, TBS, CMS, Ajah routes",
    },
    # UK
    "national_express": {
        "name": "National Express",
        "booking_url": "https://www.nationalexpress.com",
        "type": "standard",
        "country": "United Kingdom",
        "cities": ["London", "Birmingham", "Manchester", "Bristol", "Edinburgh"],
    },
    "megabus": {
        "name": "Megabus",
        "booking_url": "https://uk.megabus.com",
        "type": "budget",
        "country": "United Kingdom",
        "cities": ["London", "Manchester", "Edinburgh", "Glasgow", "Birmingham"],
    },
    "flixbus": {
        "name": "FlixBus",
        "booking_url": "https://www.flixbus.com",
        "type": "budget",
        "country": "international",
        "cities": [],
        "note": "Europe-wide intercity bus network",
    },
}

BUS_ROUTES: dict[str, dict] = {
    "lagos_abuja": {
        "distance_km": 750, "duration": "9–12 hours",
        "operators": ["GIGM", "ABC Transport", "Peace Mass", "Chisco", "Young Shall Grow"],
        "note": "Most popular intercity route. Night buses available. Check operator websites for current prices.",
    },
    "lagos_benin city": {
        "distance_km": 305, "duration": "4–6 hours",
        "operators": ["GIGM", "ABC Transport", "Chisco", "Young Shall Grow"],
    },
    "lagos_port harcourt": {
        "distance_km": 600, "duration": "8–10 hours",
        "operators": ["GIGM", "ABC Transport", "Chisco", "Young Shall Grow"],
    },
    "lagos_owerri": {
        "distance_km": 510, "duration": "7–9 hours",
        "operators": ["GIGM", "Peace Mass", "Chisco"],
    },
    "lagos_enugu": {
        "distance_km": 535, "duration": "7–10 hours",
        "operators": ["Peace Mass", "ABC Transport", "Cross Country"],
    },
    "abuja_jos": {
        "distance_km": 290, "duration": "3–4 hours",
        "operators": ["Peace Mass", "ABC Transport"],
    },
    "abuja_enugu": {
        "distance_km": 350, "duration": "5–7 hours",
        "operators": ["Peace Mass", "ABC Transport", "Cross Country"],
    },
    "benin city_lagos": {
        "distance_km": 305, "duration": "4–6 hours",
        "operators": ["GIGM", "ABC Transport", "Chisco", "Young Shall Grow"],
    },
}

BUS_TERMINAL_COORDS: dict[str, dict] = {
    "Jibowu Lagos": {"city": "Lagos", "country": "Nigeria", "coords": (6.5194, 3.3674)},
    "Ojota Lagos": {"city": "Lagos", "country": "Nigeria", "coords": (6.5833, 3.3833)},
    "Mazamaza Lagos": {"city": "Lagos", "country": "Nigeria", "coords": (6.4632, 3.3295)},
    "Utako Abuja": {"city": "Abuja", "country": "Nigeria", "coords": (9.0633, 7.4300)},
    "Jabi Abuja": {"city": "Abuja", "country": "Nigeria", "coords": (9.0500, 7.4150)},
    "Rumuokoro PH": {"city": "Port Harcourt", "country": "Nigeria", "coords": (4.8563, 6.9781)},
    "Upper Iweka Onitsha": {"city": "Onitsha", "country": "Nigeria", "coords": (6.1431, 6.7867)},
    "Holy Ghost Enugu": {"city": "Enugu", "country": "Nigeria", "coords": (6.4429, 7.4929)},
    "Owerri Terminal": {"city": "Owerri", "country": "Nigeria", "coords": (5.4840, 7.0333)},
    "Benin Terminal": {"city": "Benin City", "country": "Nigeria", "coords": (6.3350, 5.6279)},
    "Victoria Coach London": {"city": "London", "country": "United Kingdom", "coords": (51.4920, -0.1483)},
}

CAR_HIRE_PROVIDERS: dict[str, dict] = {
    # Nigeria
    "bolt_ng": {
        "name": "Bolt (formerly Taxify)",
        "booking_url": "https://bolt.eu",
        "country": "Nigeria",
        "car_types": ["sedan", "suv", "xl"],
        "type": "ride_hailing",
        "note": "On-demand rides, not traditional car hire. Best for city-to-city trips. Check app for current prices.",
    },
    "uber_ng": {
        "name": "Uber Nigeria",
        "booking_url": "https://www.uber.com",
        "country": "Nigeria",
        "car_types": ["uberx", "comfort", "xl"],
        "type": "ride_hailing",
        "note": "On-demand rides. Check app for current prices.",
    },
    "avis_ng": {
        "name": "Avis Nigeria",
        "booking_url": "https://www.avis.com/en/locations/ng",
        "country": "Nigeria",
        "car_types": ["sedan", "suv", "luxury", "minibus"],
        "note": "Check website for current daily rates.",
    },
    "hertz_ng": {
        "name": "Hertz Nigeria",
        "booking_url": "https://www.hertz.com",
        "country": "Nigeria",
        "car_types": ["sedan", "suv", "luxury"],
        "note": "Check website for current daily rates.",
    },
    # International
    "avis": {
        "name": "Avis", "booking_url": "https://www.avis.com",
        "international": True, "car_types": ["sedan", "suv", "luxury", "minibus"],
    },
    "hertz": {
        "name": "Hertz", "booking_url": "https://www.hertz.com",
        "international": True, "car_types": ["sedan", "suv", "luxury"],
    },
    "europcar": {
        "name": "Europcar", "booking_url": "https://www.europcar.com",
        "international": True, "car_types": ["sedan", "suv", "luxury", "minibus"],
    },
    "sixt": {
        "name": "Sixt", "booking_url": "https://www.sixt.com",
        "international": True, "car_types": ["sedan", "suv", "luxury", "sports"],
    },
}


def _parse_iso_duration(duration: str) -> int:
    """Parse ISO 8601 duration (PT2H30M) to minutes."""
    if not duration or not duration.startswith("PT"):
        return 0
    minutes = 0
    current = ""
    for char in duration[2:]:
        if char == "H":
            minutes += int(current or 0) * 60
            current = ""
        elif char == "M":
            minutes += int(current or 0)
            current = ""
        elif char.isdigit():
            current += char
    return minutes
