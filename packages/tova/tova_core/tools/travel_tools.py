"""
Travel tools — flight search, comparison, and booking guidance.

Tova searches for flights, compares prices, helps the user pick the best
option, and provides a direct link to book on the airline's website.

NO automated payment. NO automated booking. The user completes the
booking themselves — Tova just finds the best deal and guides them.

Workflow:
    1. User: "I need a flight to Port Harcourt on March 30th"
    2. Tova resolves airports → LOS → PHC
    3. Tova searches flights (SerpAPI/Amadeus/offline)
    4. Tova presents options sorted by price/time
    5. User picks one
    6. Tova gives them the booking link + checklist of what they need
    7. Tova saves the trip to their calendar (optional)
"""

from __future__ import annotations

import logging
from datetime import datetime
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.providers.travel import BaseTravelProvider
from tova_core.providers.calendar import BaseCalendarProvider

logger = logging.getLogger(__name__)


def build_travel_tools(
    store: BaseStore,
    travel_provider: BaseTravelProvider,
    calendar_provider: BaseCalendarProvider | None = None,
) -> list:
    """Build travel/flight search tools.

    These tools let the agent search for flights, compare options,
    save travel plans, and guide users through booking.
    """

    @tool
    async def find_nearest_airport(
        latitude: float,
        longitude: float,
        limit: int = 3,
    ) -> dict:
        """Find the nearest airports to the user's current GPS location.

        ALWAYS call this first when the user asks about flights but doesn't
        specify a departure city. Uses their GPS coordinates to find the
        closest airports, so we search from the right place — not a city
        hundreds of miles away.

        Args:
            latitude: User's current latitude
            longitude: User's current longitude
            limit: Max number of nearby airports to return (default 3)
        """
        try:
            airports = await travel_provider.find_nearest_airports(
                latitude=latitude,
                longitude=longitude,
                limit=limit,
            )
            if airports:
                return {
                    "nearest_airports": airports,
                    "recommended": airports[0]["code"],
                    "recommended_city": airports[0]["city"],
                    "recommended_distance_km": airports[0]["distance_km"],
                    "guidance": (
                        f"The user is closest to {airports[0]['city']} ({airports[0]['code']}) "
                        f"airport, {airports[0]['distance_km']}km away. Use this as the departure "
                        f"airport unless the user specifies otherwise."
                    ),
                }
            return {
                "nearest_airports": [],
                "guidance": "Could not determine nearest airport. Ask the user which city they're departing from.",
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def resolve_airport(
        city_or_code: str,
    ) -> dict:
        """Resolve a city name to its IATA airport code.

        Use this before searching flights to get the correct airport codes.
        Handles common names, abbreviations, and aliases.

        Args:
            city_or_code: City name (e.g., "Port Harcourt", "Lagos") or IATA code (e.g., "PHC")
        """
        try:
            result = await travel_provider.get_airport_code(city_or_code)
            return result
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def search_flights(
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = "",
        adults: int = 1,
        children: int = 0,
        cabin_class: str = "economy",
        max_results: int = 5,
        sort_by: str = "price",
        time_preference: str = "",
    ) -> dict:
        """Search for available flights between two cities.

        Returns flight options with prices, times, airlines, and booking links.
        The user books directly on the airline's website — we do NOT handle payment.

        CRITICAL PRICE RULE:
        - ONLY show prices that come from live search results (source != "offline")
        - NEVER make up, guess, or estimate prices
        - If no live prices available, tell the user to check the booking URLs
        - Always mention the source of the price data

        WORKFLOW:
        1. If user has GPS coordinates and didn't specify departure city,
           FIRST call find_nearest_airport to detect their closest airport
        2. Resolve city names to airport codes using resolve_airport
        3. Search flights with the correct origin
        4. Present results clearly: airline, time, duration, stops, price
        5. Highlight the cheapest and the fastest options
        6. When user picks a flight, give them the booking_url
        7. Offer to save the trip to their calendar

        Args:
            origin: Departure city name or IATA airport code
            destination: Arrival city name or IATA airport code
            departure_date: Date in YYYY-MM-DD format
            return_date: Return date for round trips (empty = one-way)
            adults: Number of adult passengers (default 1)
            children: Number of child passengers (default 0)
            cabin_class: economy, premium_economy, business, first
            max_results: Maximum number of results to show (default 5)
            sort_by: Sort results by: price, duration, or departure_time
            time_preference: Filter by time of day: morning (before 12pm), afternoon (12-5pm), evening (after 5pm), or empty for any
        """
        try:
            results = await travel_provider.search_flights(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                adults=adults,
                children=children,
                cabin_class=cabin_class,
                max_results=max_results,
                sort_by=sort_by,
                time_preference=time_preference,
            )

            flights = results.get("flights", [])
            if flights:
                # Add summary stats — only from live data
                prices = [f["price"] for f in flights if f.get("price")]
                if prices:
                    results["price_summary"] = {
                        "cheapest": min(prices),
                        "most_expensive": max(prices),
                        "currency": flights[0].get("currency", "NGN"),
                        "source": results.get("source", "live"),
                    }
                results["guidance"] = (
                    "These are LIVE prices from the search API. Present them clearly: "
                    "airline, time, duration, stops, price. Highlight the cheapest. "
                    "When the user picks a flight, give them the booking_url. "
                    "Note: prices may change — recommend booking soon."
                )
            elif results.get("airlines"):
                # Offline mode — airline directory, NO prices
                results["guidance"] = (
                    "No live prices available. Show the airlines that fly this route "
                    "and the manual_search_urls where they can check CURRENT prices. "
                    "Do NOT quote any prices. Recommend Google Flights for comparison."
                )
            else:
                results["guidance"] = (
                    "No flights found for this route/date. Suggest the user try: "
                    "different dates, nearby airports, or connecting flights."
                )

            return results
        except Exception as e:
            return {"error": str(e)}

    # ── Train Search ────────────────────────────────────────────

    @tool
    async def search_trains(
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = "",
        passengers: int = 1,
        train_class: str = "standard",
        max_results: int = 5,
        sort_by: str = "price",
        time_preference: str = "",
    ) -> dict:
        """Search for train routes between two cities.

        Returns train options with operators, schedules, and booking links.
        The user books directly on the train operator's website — we do NOT handle payment.

        CRITICAL PRICE RULE:
        - ONLY quote prices found in web_results snippets (with source URL)
        - NEVER make up, guess, or estimate train fares
        - If no prices in web_results, tell user to check the booking URL
        - Prices change frequently — always direct users to verify on the operator's site

        WORKFLOW:
        1. If user's GPS is available, call find_nearest_airport first to determine
           their nearest city (train stations are in the same cities)
        2. Search trains for the route
        3. Present results: operator, departure time, duration, price, class
        4. When user picks, give them the booking_url
        5. Offer to save to calendar

        Args:
            origin: Departure city or station name
            destination: Arrival city or station name
            departure_date: Date in YYYY-MM-DD format
            return_date: For round trips (empty = one-way)
            passengers: Number of passengers
            train_class: standard, first, business
            max_results: Maximum results to show
            sort_by: price, duration, or departure_time
            time_preference: morning, afternoon, evening, or empty for any
        """
        try:
            results = await travel_provider.search_trains(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                passengers=passengers,
                train_class=train_class,
                max_results=max_results,
                sort_by=sort_by,
                time_preference=time_preference,
            )
            if results.get("operators"):
                results["guidance"] = (
                    "Present train operators and route info to the user. "
                    "Show duration, price range, and booking URLs. "
                    "If the route is available, recommend the operator. "
                    "Offer to save the trip to their calendar."
                )
            return results
        except Exception as e:
            return {"error": str(e)}

    # ── Bus / Road Transport ─────────────────────────────────────

    @tool
    async def search_buses(
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = "",
        passengers: int = 1,
        max_results: int = 5,
        sort_by: str = "price",
        time_preference: str = "",
    ) -> dict:
        """Search for intercity bus routes between two cities.

        Returns bus operators, routes, and booking links.
        The user books directly — we do NOT handle payment.

        CRITICAL PRICE RULE:
        - ONLY quote prices found in web_results snippets (with source URL)
        - NEVER make up, guess, or estimate bus fares
        - If no prices in web_results, tell user to check operator websites or call them
        - Prices change by season, demand, and bus type — always verify

        Use this when:
        - User asks about bus travel between cities
        - Flight is too expensive and user wants cheaper options
        - Route has no train or flight service
        - User prefers road travel

        Args:
            origin: Departure city
            destination: Arrival city
            departure_date: Date in YYYY-MM-DD format
            return_date: For round trips (empty = one-way)
            passengers: Number of passengers
            max_results: Maximum results to show
            sort_by: price, duration, or departure_time
            time_preference: morning, afternoon, evening, or empty for any
        """
        try:
            results = await travel_provider.search_buses(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                passengers=passengers,
                max_results=max_results,
                sort_by=sort_by,
                time_preference=time_preference,
            )
            if results.get("operators"):
                # Highlight operators that serve both cities
                direct = [o for o in results["operators"] if o.get("serves_route")]
                results["direct_operators"] = len(direct)
                results["guidance"] = (
                    "Present bus operators to the user. Highlight ones that serve "
                    "the exact route (serves_route=true). Show price range, duration, "
                    "and booking URLs. Mention phone numbers for operators that have them — "
                    "many Nigerian bus bookings are done by phone or at the terminal."
                )
            if results.get("route_info"):
                results["guidance"] = (
                    f"This is a known route: {results['route_info'].get('distance_km', '')}km, "
                    f"takes about {results['route_info'].get('duration', '')}. "
                    f"Price range: {results['route_info'].get('price_range', '')}. "
                    "Present operators and let the user pick."
                )
            return results
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def search_car_hire(
        pickup_location: str,
        dropoff_location: str = "",
        pickup_date: str = "",
        dropoff_date: str = "",
        car_type: str = "any",
        max_results: int = 5,
    ) -> dict:
        """Search for car hire / rental options.

        Returns car hire providers and booking links.
        Also includes ride-hailing options (Bolt, Uber) for intercity trips.

        CRITICAL PRICE RULE:
        - NEVER quote car hire prices — they vary by date, car type, and availability
        - Direct users to the provider's website or app for current rates
        - For Bolt/Uber, mention they can check the app for fare estimates

        Use this when:
        - User wants to rent a car for their trip
        - User prefers private/comfortable travel
        - Route is not well served by buses or trains
        - User needs flexibility at destination

        Args:
            pickup_location: City or area for pickup
            dropoff_location: City for return (empty = same as pickup)
            pickup_date: Date in YYYY-MM-DD format
            dropoff_date: Return date (empty = same day)
            car_type: any, sedan, suv, minibus, luxury
            max_results: Maximum results to show
        """
        try:
            results = await travel_provider.search_car_hire(
                pickup_location=pickup_location,
                dropoff_location=dropoff_location,
                pickup_date=pickup_date,
                dropoff_date=dropoff_date,
                car_type=car_type,
                max_results=max_results,
            )
            results["guidance"] = (
                "Present car hire options. Include both traditional rental companies "
                "and ride-hailing (Bolt/Uber) for intercity trips. Show price ranges "
                "and booking links. For Bolt/Uber, note they're on-demand — no advance booking needed."
            )
            return results
        except Exception as e:
            return {"error": str(e)}

    # ── Multi-Modal Comparison ───────────────────────────────────

    @tool
    async def compare_transport(
        origin: str,
        destination: str,
        departure_date: str,
        passengers: int = 1,
    ) -> dict:
        """Compare ALL transport options for a route: flights, trains, and buses side by side.

        CRITICAL PRICE RULE:
        - ONLY show prices from live search results
        - If a mode has no live prices, say "check [website] for current fares"
        - NEVER fabricate a price comparison with made-up numbers

        Use this when:
        - User says "what's the best way to get to X?"
        - User wants to compare prices across modes
        - User is flexible about transport type
        - You want to give the user a complete picture

        Searches flights, trains, and buses in PARALLEL and returns a comparison.

        Args:
            origin: Departure city
            destination: Arrival city
            departure_date: Date in YYYY-MM-DD format
            passengers: Number of passengers
        """
        try:
            results = await travel_provider.compare_transport(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                passengers=passengers,
            )
            results["guidance"] = (
                "Present a clear comparison table: Flight vs Train vs Bus. "
                "For each mode, show: cheapest price, travel time, convenience, "
                "and booking link. Recommend the best option based on the user's "
                "priorities (if they mentioned speed, recommend flight; if budget, "
                "recommend bus; if comfort, recommend train or car)."
            )
            return results
        except Exception as e:
            return {"error": str(e)}

    # ── Save Travel Plan (all modes) ─────────────────────────────

    @tool
    async def save_travel_plan(
        user_id: str,
        transport_mode: str,
        operator: str,
        origin: str,
        destination: str,
        departure_date: str,
        departure_time: str,
        arrival_time: str = "",
        booking_url: str = "",
        price: float = 0,
        currency: str = "NGN",
        reference_number: str = "",
        notes: str = "",
    ) -> dict:
        """Save a travel plan for the user (flight, train, bus, or car).

        Stores the trip details and creates a calendar event.
        Call this when the user confirms which option they want.

        Args:
            user_id: The user's ID
            transport_mode: flight, train, bus, or car
            operator: Airline, train operator, bus company, or car hire company name
            origin: Departure city/station/airport
            destination: Arrival city/station/airport
            departure_date: Date in YYYY-MM-DD format
            departure_time: Departure time (e.g., "07:30")
            arrival_time: Arrival time (e.g., "08:45")
            booking_url: URL where user can book
            price: Price (for reference only, no payment)
            currency: Price currency (default NGN)
            reference_number: Flight number, train ID, or booking reference
            notes: Any additional notes
        """
        try:
            mode_labels = {
                "flight": "Flight", "train": "Train",
                "bus": "Bus", "car": "Car Hire",
            }
            mode_label = mode_labels.get(transport_mode, transport_mode.title())
            location_suffix = {
                "flight": "Airport", "train": "Station",
                "bus": "Terminal", "car": "",
            }

            travel_plan = {
                "type": transport_mode,
                "operator": operator,
                "reference": reference_number,
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "booking_url": booking_url,
                "price": price,
                "currency": currency,
                "notes": notes,
                "status": "planned",
                "created_at": datetime.now().isoformat(),
            }

            title = f"{mode_label}: {origin} → {destination} ({operator}"
            if reference_number:
                title += f" {reference_number}"
            title += ")"

            # Save to store
            try:
                plan_id = await store.save_todo(user_id, {
                    "title": title,
                    "description": (
                        f"Mode: {mode_label}\n"
                        f"Operator: {operator}\n"
                        f"Departure: {departure_date} at {departure_time}\n"
                        f"Arrival: {arrival_time}\n"
                        f"Price: {currency} {price:,.0f}\n"
                        f"Book here: {booking_url}\n"
                        f"{notes}"
                    ),
                    "category": "travel",
                    "priority": "high",
                    "due_date": departure_date,
                    "status": "pending",
                    "metadata": travel_plan,
                })
                travel_plan["id"] = plan_id
            except NotImplementedError:
                travel_plan["id"] = f"trip_{departure_date}_{reference_number or operator}"

            # Create calendar event
            calendar_created = False
            if calendar_provider:
                try:
                    dep_dt = f"{departure_date}T{departure_time}:00" if departure_time else f"{departure_date}T00:00:00"
                    arr_dt = f"{departure_date}T{arrival_time}:00" if arrival_time else ""
                    suffix = location_suffix.get(transport_mode, "")
                    loc = f"{origin} {suffix} → {destination} {suffix}".strip()

                    await calendar_provider.create_event(user_id, {
                        "title": f"{mode_label}: {origin} → {destination}",
                        "description": (
                            f"Operator: {operator}\n"
                            f"Reference: {reference_number}\n"
                            f"Price: {currency} {price:,.0f}\n"
                            f"Booking: {booking_url}\n"
                            f"Status: Not yet booked"
                        ),
                        "start": dep_dt,
                        "end": arr_dt or dep_dt,
                        "location": loc,
                    })
                    calendar_created = True
                except Exception as cal_err:
                    logger.warning(f"Failed to create calendar event: {cal_err}")

            # Mode-specific next steps
            next_steps = [f"Visit {booking_url} to complete your booking" if booking_url
                          else f"Contact {operator} to complete your booking"]
            next_steps.append("Have your valid ID ready")

            if transport_mode == "flight":
                next_steps.extend([
                    "Check baggage allowance on the airline's site",
                    f"Arrive at {origin} airport at least 1.5 hours before departure",
                ])
            elif transport_mode == "train":
                next_steps.extend([
                    "Arrive at the station at least 30 minutes before departure",
                    "Check if there's assigned seating or open seating",
                ])
            elif transport_mode == "bus":
                next_steps.extend([
                    "Arrive at the terminal at least 30 minutes early",
                    "Pack light — overhead luggage space may be limited",
                    "Bring water and snacks for long journeys",
                ])
            elif transport_mode == "car":
                next_steps.extend([
                    "Confirm pickup time and location with the company",
                    "Check if insurance is included",
                    "Bring your driver's license (for self-drive rentals)",
                ])

            return {
                "saved": True,
                "plan_id": travel_plan.get("id", ""),
                "summary": f"{mode_label} ({operator}): {origin} → {destination} on {departure_date} at {departure_time}",
                "calendar_event_created": calendar_created,
                "booking_url": booking_url,
                "next_steps": next_steps,
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def get_travel_checklist(
        trip_type: str = "domestic",
        transport_mode: str = "flight",
        destination_country: str = "",
    ) -> dict:
        """Get a travel preparation checklist based on trip and transport type.

        Args:
            trip_type: domestic or international
            transport_mode: flight, train, bus, or car
            destination_country: For international trips, the destination country
        """
        common = [
            "Valid government-issued ID (national ID card or driver's license)",
            "Print or screenshot your booking confirmation / e-ticket",
            "Charge your phone",
            "Pack essentials (charger, medication, documents)",
        ]

        mode_specific = {
            "flight": [
                "Arrive at the airport at least 1.5 hours before departure",
                "Check airline's baggage policy (weight limits, carry-on size)",
                "Download the airline's app for mobile boarding pass",
            ],
            "train": [
                "Arrive at the station at least 30 minutes before departure",
                "Check platform number on departure boards",
                "Pack snacks and entertainment for the journey",
            ],
            "bus": [
                "Arrive at the terminal at least 30 minutes early",
                "Pack light — overhead space may be limited",
                "Bring water, snacks, and a neck pillow for long trips",
                "Keep valuables in a bag you can keep with you",
                "Charge your phone fully — buses may not have power outlets",
            ],
            "car": [
                "Confirm pickup time and location",
                "Check if insurance and fuel are included in the price",
                "Save the operator's phone number for emergencies",
                "For self-drive: bring driver's license, check spare tire",
                "Plan rest stops for journeys over 4 hours",
            ],
        }

        checklist = common + mode_specific.get(transport_mode, [])

        if trip_type == "international":
            checklist = [
                "Valid international passport (check expiry — at least 6 months validity)",
                "Visa for destination country (if required)",
                f"Check entry requirements for {destination_country or 'your destination'}",
                "Travel insurance",
                "Foreign currency or travel card",
                "Notify your bank about international travel",
            ] + checklist + [
                "Check if you need vaccinations (Yellow Fever card for some countries)",
            ]
        else:
            checklist += [
                "Check weather at your destination",
                "Save emergency contacts for your destination city",
                "Arrange transportation at arrival",
            ]

        return {
            "trip_type": trip_type,
            "transport_mode": transport_mode,
            "destination": destination_country,
            "checklist": checklist,
            "items_count": len(checklist),
        }

    @tool
    async def list_travel_plans(
        user_id: str,
    ) -> dict:
        """List the user's saved travel plans (flights, trains, buses, car hire).

        Shows upcoming and past trips across all transport modes.

        Args:
            user_id: The user whose travel plans to list
        """
        try:
            todos = await store.list_todos(user_id)
            keywords = ("flight", "train", "bus", "car hire", "travel")
            travel_plans = [
                {
                    "id": t.get("id", ""),
                    "title": t.get("title", ""),
                    "description": t.get("description", ""),
                    "due_date": t.get("due_date", ""),
                    "status": t.get("status", ""),
                    "metadata": t.get("metadata", {}),
                }
                for t in todos
                if t.get("category") == "travel"
                or any(k in t.get("title", "").lower() for k in keywords)
            ]
            return {
                "plans": travel_plans,
                "count": len(travel_plans),
            }
        except NotImplementedError:
            return {"plans": [], "count": 0, "note": "Travel plan storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    return [
        find_nearest_airport,
        resolve_airport,
        search_flights,
        search_trains,
        search_buses,
        search_car_hire,
        compare_transport,
        save_travel_plan,
        get_travel_checklist,
        list_travel_plans,
    ]
