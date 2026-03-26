"""
Travel & lifestyle provider — abstract interface for transport, accommodation,
and entertainment search.

Covers flights, trains, vehicles (buses, car hire), accommodations (Airbnb,
hotels), and attractions (amusement parks, events, activities).

Tova searches, compares prices, and guides the user to book.
No automated payment — Tova presents options and provides booking links.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTravelProvider(ABC):
    """Abstract travel & lifestyle search provider.

    Supports flights, trains, road transport, accommodations, and
    attractions/entertainment. All modes follow the same pattern:
    search → compare → present booking link → user books themselves.
    """

    # ── Flights ───────────────────────────────────────────────

    @abstractmethod
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
        """Search for flights.

        Args:
            origin: Departure city or IATA airport code
            destination: Arrival city or IATA code
            departure_date: YYYY-MM-DD
            return_date: For round trips (empty = one-way)
            adults: Number of adult passengers
            children: Number of child passengers
            cabin_class: economy, premium_economy, business, first
            max_results: Max results
            sort_by: price, duration, departure_time
            time_preference: morning, afternoon, evening, any
        """
        ...

    @abstractmethod
    async def get_airport_code(self, city_or_query: str) -> dict:
        """Resolve a city name to IATA airport code(s)."""
        ...

    async def find_nearest_airports(
        self,
        latitude: float,
        longitude: float,
        limit: int = 3,
        max_km: float = 500,
    ) -> list[dict]:
        """Find nearest airports to user's GPS location."""
        raise NotImplementedError("Nearest airport search not available")

    async def get_flight_details(self, flight_id: str) -> dict:
        """Get detailed info for a specific flight offer."""
        raise NotImplementedError("Flight details not available")

    # ── Trains ────────────────────────────────────────────────

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
        """Search for train routes.

        Args:
            origin: Departure city or station name
            destination: Arrival city or station name
            departure_date: YYYY-MM-DD
            return_date: For round trips (empty = one-way)
            passengers: Number of passengers
            train_class: standard, first, business
            max_results: Max results
            sort_by: price, duration, departure_time
            time_preference: morning, afternoon, evening, any

        Returns:
            dict with: trains (list), search_metadata, stations (if offline)
        """
        raise NotImplementedError("Train search not configured")

    async def get_train_station(self, city_or_query: str) -> dict:
        """Resolve a city name to train station(s)."""
        raise NotImplementedError("Train station lookup not available")

    async def find_nearest_stations(
        self,
        latitude: float,
        longitude: float,
        limit: int = 3,
        max_km: float = 200,
    ) -> list[dict]:
        """Find nearest train stations to user's GPS location."""
        raise NotImplementedError("Nearest station search not available")

    # ── Road Transport (Buses, Car Hire) ──────────────────────

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
        """Search for intercity bus routes.

        Args:
            origin: Departure city or terminal name
            destination: Arrival city or terminal name
            departure_date: YYYY-MM-DD
            return_date: For round trips (empty = one-way)
            passengers: Number of passengers
            max_results: Max results
            sort_by: price, duration, departure_time
            time_preference: morning, afternoon, evening, any

        Returns:
            dict with: buses (list), search_metadata, terminals (if offline)
        """
        raise NotImplementedError("Bus search not configured")

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
        """Search for car hire / rental options.

        Args:
            pickup_location: City or address for pickup
            dropoff_location: City or address for return (empty = same as pickup)
            pickup_date: YYYY-MM-DD
            dropoff_date: YYYY-MM-DD (empty = same day)
            car_type: any, sedan, suv, minibus, luxury
            max_results: Max results
            sort_by: price, rating
        """
        raise NotImplementedError("Car hire search not configured")

    async def find_nearest_terminals(
        self,
        latitude: float,
        longitude: float,
        transport_type: str = "bus",
        limit: int = 3,
        max_km: float = 100,
    ) -> list[dict]:
        """Find nearest bus terminals or car hire depots to user's GPS location."""
        raise NotImplementedError("Nearest terminal search not available")

    # ── Accommodations ─────────────────────────────────────────

    async def search_accommodations(
        self,
        location: str,
        checkin_date: str = "",
        checkout_date: str = "",
        guests: int = 1,
        accommodation_type: str = "any",
        max_results: int = 10,
        sort_by: str = "price",
        min_price: float = 0,
        max_price: float = 0,
    ) -> dict:
        """Search for accommodations (Airbnb, hotels, hostels, etc.).

        Args:
            location: City, area, or address to search
            checkin_date: YYYY-MM-DD
            checkout_date: YYYY-MM-DD
            guests: Number of guests
            accommodation_type: any, apartment, hotel, hostel, villa, resort, guesthouse
            max_results: Max results
            sort_by: price, rating, distance
            min_price: Minimum price per night (0 = no min)
            max_price: Maximum price per night (0 = no max)

        Returns:
            dict with: accommodations (list), search_metadata, web_results
        """
        raise NotImplementedError("Accommodation search not configured")

    # ── Attractions & Entertainment ────────────────────────────

    async def search_attractions(
        self,
        location: str,
        category: str = "any",
        date: str = "",
        max_results: int = 10,
        sort_by: str = "rating",
    ) -> dict:
        """Search for attractions, activities, and entertainment.

        Args:
            location: City or area to search
            category: any, amusement_park, museum, tour, adventure, waterpark,
                      zoo, nightlife, restaurant, shopping, spa, landmark
            date: YYYY-MM-DD (for time-specific events)
            max_results: Max results
            sort_by: rating, price, distance

        Returns:
            dict with: attractions (list), search_metadata, web_results
        """
        raise NotImplementedError("Attraction search not configured")

    # ── Multi-modal ───────────────────────────────────────────

    async def compare_transport(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: int = 1,
    ) -> dict:
        """Compare all transport modes for a route.

        Searches flights, trains, and buses in parallel and returns
        a side-by-side comparison of price, duration, and convenience.
        """
        raise NotImplementedError("Multi-modal comparison not configured")

    async def close(self) -> None:
        """Clean up resources."""
        pass
