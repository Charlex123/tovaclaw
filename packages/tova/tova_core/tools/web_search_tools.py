"""
Web search tools — Tova's universal knowledge engine.

Tova NEVER says "I don't know" or "I can't help with that" for any
searchable topic. Instead, she searches the web for current, accurate
information and presents it to the user.

This tool is Tova's fallback for ANYTHING not covered by specialized tools:
- Product prices, reviews, comparisons
- Accommodation (Airbnb, hotels, hostels)
- Attractions, amusement parks, events, activities
- Restaurants, nightlife, shopping
- News, weather, sports scores
- How-to guides, tutorials
- Local services, businesses
- ANY question the user might have

RULE: If Tova doesn't have a specialized tool for the query, she uses
search_web. She NEVER responds with "I don't know" or "I can't find that".
"""

from __future__ import annotations

import logging
import os

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def _serpapi_search(query: str, num: int = 10, gl: str = "", **extra) -> dict:
    """Run a Google search via SerpAPI and return parsed results."""
    api_key = os.environ.get("SERPAPI_API_KEY", "")
    if not api_key:
        return {"error": "SERPAPI_API_KEY not set", "results": []}

    client = await _get_client()
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num,
    }
    if gl:
        params["gl"] = gl
    params.update(extra)

    resp = await client.get("https://serpapi.com/search", params=params)
    resp.raise_for_status()
    data = resp.json()

    results = []

    # Answer box (often has direct answers, prices, etc.)
    answer_box = data.get("answer_box")
    if answer_box:
        results.append({
            "title": answer_box.get("title", "Featured Answer"),
            "snippet": answer_box.get("snippet", answer_box.get("answer", "")),
            "link": answer_box.get("link", ""),
            "source": "Google Answer Box",
            "type": "answer_box",
        })

    # Knowledge graph
    kg = data.get("knowledge_graph")
    if kg:
        results.append({
            "title": kg.get("title", ""),
            "snippet": kg.get("description", ""),
            "link": kg.get("website", kg.get("source", {}).get("link", "")),
            "source": "Google Knowledge Graph",
            "type": "knowledge_graph",
            "extra": {
                k: v for k, v in kg.items()
                if k in ("rating", "review_count", "address", "phone",
                         "hours", "price", "type", "attributes")
            },
        })

    # Organic results
    for item in data.get("organic_results", []):
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "link": item.get("link", ""),
            "source": item.get("displayed_link", ""),
            "type": "organic",
        })

    # Local results (restaurants, businesses, etc.)
    local_results = data.get("local_results", {}).get("places", [])
    for place in local_results[:5]:
        results.append({
            "title": place.get("title", ""),
            "snippet": f"Rating: {place.get('rating', 'N/A')} ({place.get('reviews', 0)} reviews). {place.get('type', '')}. {place.get('address', '')}",
            "link": place.get("link", place.get("place_id_search", "")),
            "source": "Google Local",
            "type": "local",
            "extra": {
                "rating": place.get("rating"),
                "reviews": place.get("reviews"),
                "price": place.get("price"),
                "address": place.get("address"),
                "phone": place.get("phone"),
                "hours": place.get("hours"),
                "type": place.get("type"),
                "thumbnail": place.get("thumbnail"),
            },
        })

    # Top stories / news
    for story in data.get("top_stories", [])[:3]:
        results.append({
            "title": story.get("title", ""),
            "snippet": story.get("snippet", story.get("date", "")),
            "link": story.get("link", ""),
            "source": story.get("source", "News"),
            "type": "news",
        })

    return {
        "results": results,
        "total": len(results),
        "search_query": query,
    }


def build_web_search_tools() -> list:
    """Build universal web search tools.

    These give Tova the ability to answer ANY question by searching
    the web for current, accurate information.
    """

    @tool
    async def search_web(
        query: str,
        category: str = "general",
        location: str = "",
        num_results: int = 8,
    ) -> dict:
        """Search the web for ANY information the user needs.

        THIS IS YOUR MOST IMPORTANT FALLBACK TOOL. Use it whenever:
        - You don't have a specialized tool for the query
        - You're not sure about something and need current data
        - The user asks about ANYTHING you don't have built-in knowledge for
        - You need current prices, availability, reviews, or ratings
        - The user asks about local services, businesses, events
        - You need to verify or update information

        CRITICAL RULES:
        - NEVER say "I don't know" or "I can't help with that" — SEARCH FIRST
        - NEVER say "I'm not sure" without searching — SEARCH FIRST
        - NEVER give outdated information when you can search for current data
        - ALWAYS present search results clearly with sources
        - If one search doesn't find what you need, try a different query

        Examples of when to use:
        - "What's the weather in Lagos?" → search
        - "Best restaurants near me" → search with location
        - "Airbnb in Lekki" → search
        - "Amusement parks in Lagos" → search
        - "iPhone 16 price in Nigeria" → search
        - "How to make jollof rice" → search
        - "Latest Premier League scores" → search
        - "Best schools in Abuja" → search
        - "Visa requirements for UK" → search

        Args:
            query: What to search for — be specific for better results
            category: Hint for result type: general, accommodation, attraction,
                      restaurant, shopping, news, how_to, local_service,
                      entertainment, education, health, technology, sports
            location: Location context (e.g., "Lagos", "Nigeria") for local results
            num_results: Number of results to return (default 8)
        """
        # Build an optimized search query based on category
        search_query = query
        if location and location.lower() not in query.lower():
            search_query = f"{query} {location}"

        category_suffixes = {
            "accommodation": "booking availability price per night",
            "attraction": "tickets hours reviews",
            "restaurant": "menu reviews rating near",
            "shopping": "price buy online",
            "news": "latest news today",
            "how_to": "how to guide tutorial step by step",
            "local_service": "near me reviews contact",
            "entertainment": "tickets events shows schedule",
            "education": "admission requirements fees",
            "health": "symptoms treatment medical advice",
            "technology": "specs review price comparison",
            "sports": "score results schedule standings",
        }
        suffix = category_suffixes.get(category, "")
        if suffix and not any(word in query.lower() for word in suffix.split()[:2]):
            search_query = f"{query} {suffix}"

        # Detect country for localization
        gl = ""
        loc_lower = (location or query).lower()
        if any(w in loc_lower for w in ["nigeria", "lagos", "abuja", "naira", "ngn"]):
            gl = "ng"
        elif any(w in loc_lower for w in ["uk", "london", "britain", "england"]):
            gl = "uk"
        elif any(w in loc_lower for w in ["usa", "us", "america", "new york"]):
            gl = "us"

        try:
            data = await _serpapi_search(search_query, num=num_results, gl=gl)
            results = data.get("results", [])

            if not results:
                # Retry with a simpler query
                data = await _serpapi_search(query, num=num_results, gl=gl)
                results = data.get("results", [])

            return {
                "results": results,
                "total": len(results),
                "search_query": search_query,
                "category": category,
                "guidance": (
                    "Present these search results clearly to the user. "
                    "Extract the most relevant information from the snippets. "
                    "Include source links so the user can verify. "
                    "If the results contain prices, ratings, or reviews, highlight them. "
                    "NEVER add information that isn't in the search results."
                ),
            }
        except Exception as e:
            return {"error": str(e), "search_query": search_query}

    @tool
    async def search_accommodations(
        query: str,
        location: str,
        checkin_date: str = "",
        checkout_date: str = "",
        guests: int = 1,
        accommodation_type: str = "any",
        max_results: int = 8,
    ) -> dict:
        """Search for accommodations — Airbnb, hotels, hostels, resorts, guesthouses.

        Returns current listings with prices, ratings, and booking links from the web.

        CRITICAL PRICE RULE:
        - ONLY quote prices found in search results (with source)
        - NEVER make up or estimate accommodation prices
        - Always direct users to the booking link for final pricing

        Use this when:
        - User asks about places to stay, hotels, Airbnb, accommodation
        - User is planning a trip and needs lodging
        - User asks about short-term rentals, vacation homes

        Args:
            query: Additional search terms (e.g., "luxury", "budget", "with pool")
            location: City or area (e.g., "Lekki Lagos", "Victoria Island")
            checkin_date: Check-in date YYYY-MM-DD (optional)
            checkout_date: Check-out date YYYY-MM-DD (optional)
            guests: Number of guests
            accommodation_type: any, airbnb, hotel, hostel, resort, villa, guesthouse, apartment
            max_results: Max results to return
        """
        type_map = {
            "airbnb": "Airbnb",
            "hotel": "hotel",
            "hostel": "hostel",
            "resort": "resort",
            "villa": "villa",
            "guesthouse": "guest house",
            "apartment": "apartment short-let",
        }
        type_str = type_map.get(accommodation_type, "accommodation hotel Airbnb")

        search_query = f"{type_str} {location}"
        if query and query.lower() not in ("any", ""):
            search_query = f"{query} {search_query}"
        if checkin_date:
            search_query += f" {checkin_date}"
        search_query += " price per night booking"

        gl = ""
        loc_lower = location.lower()
        if any(w in loc_lower for w in ["lagos", "abuja", "nigeria", "lekki", "vi", "ikoyi"]):
            gl = "ng"
        elif any(w in loc_lower for w in ["london", "uk", "manchester", "birmingham"]):
            gl = "uk"

        try:
            data = await _serpapi_search(search_query, num=max_results, gl=gl)
            results = data.get("results", [])

            # Also search specifically on Airbnb and Booking.com
            booking_platforms = [
                {"name": "Airbnb", "url": f"https://www.airbnb.com/s/{location.replace(' ', '-')}/homes",
                 "note": "Search Airbnb for apartments, homes, and unique stays"},
                {"name": "Booking.com", "url": f"https://www.booking.com/searchresults.html?ss={location.replace(' ', '+')}",
                 "note": "Search Booking.com for hotels and apartments"},
                {"name": "Hotels.com", "url": f"https://www.hotels.com/search.do?q-destination={location.replace(' ', '+')}",
                 "note": "Compare hotel prices"},
            ]

            return {
                "results": results,
                "total": len(results),
                "booking_platforms": booking_platforms,
                "search_query": search_query,
                "search_metadata": {
                    "location": location,
                    "checkin": checkin_date,
                    "checkout": checkout_date,
                    "guests": guests,
                    "type": accommodation_type,
                },
                "guidance": (
                    "Present accommodation options from the search results. "
                    "Show name, price per night (if available), rating, and booking link. "
                    "ONLY quote prices found in the results — NEVER make up prices. "
                    "Also show the direct booking platform links so the user can browse more options. "
                    "If no specific listings found, direct user to the platform URLs to search directly."
                ),
            }
        except Exception as e:
            return {"error": str(e), "search_query": search_query}

    @tool
    async def search_attractions(
        query: str,
        location: str,
        category: str = "any",
        date: str = "",
        max_results: int = 8,
    ) -> dict:
        """Search for attractions, activities, entertainment, and things to do.

        Covers amusement parks, museums, tours, adventures, waterparks, zoos,
        nightlife, restaurants, shopping, spas, landmarks, and more.

        CRITICAL RULE:
        - ONLY quote prices/hours from search results
        - NEVER guess opening hours or ticket prices
        - Always provide booking/info links

        Use this when:
        - User asks about things to do, fun activities, entertainment
        - User asks about specific attractions (amusement parks, museums, etc.)
        - User is exploring a city and wants recommendations
        - User asks about events, shows, concerts, festivals

        Args:
            query: What to search for (e.g., "amusement parks", "fun things to do")
            location: City or area to search
            category: any, amusement_park, museum, tour, adventure, waterpark,
                      zoo, nightlife, restaurant, shopping, spa, landmark,
                      cinema, concert, festival, sports_event, beach
            date: Specific date YYYY-MM-DD (for events)
            max_results: Max results to return
        """
        category_terms = {
            "amusement_park": "amusement park theme park fun park rides",
            "museum": "museum gallery exhibition",
            "tour": "tour sightseeing guided tour",
            "adventure": "adventure activities outdoor extreme sports",
            "waterpark": "water park waterpark aqua park swimming",
            "zoo": "zoo wildlife animal park aquarium",
            "nightlife": "nightlife clubs bars lounge nightclub",
            "restaurant": "best restaurants food dining",
            "shopping": "shopping mall market stores",
            "spa": "spa wellness massage relaxation",
            "landmark": "landmarks tourist attractions must-see sights",
            "cinema": "cinema movies theater showing",
            "concert": "concert live music shows events",
            "festival": "festival events happening",
            "sports_event": "sports events matches games tickets",
            "beach": "beach resort waterfront seaside",
        }
        cat_terms = category_terms.get(category, "things to do attractions activities")

        search_query = f"{cat_terms} {location}"
        if query and query.lower() not in ("any", ""):
            search_query = f"{query} {location}"
        if date:
            search_query += f" {date}"
        search_query += " tickets hours reviews"

        gl = ""
        loc_lower = location.lower()
        if any(w in loc_lower for w in ["lagos", "abuja", "nigeria"]):
            gl = "ng"
        elif any(w in loc_lower for w in ["london", "uk"]):
            gl = "uk"

        try:
            data = await _serpapi_search(search_query, num=max_results, gl=gl)
            results = data.get("results", [])

            # Helpful discovery platforms
            platforms = [
                {"name": "TripAdvisor", "url": f"https://www.tripadvisor.com/Search?q={location.replace(' ', '+')}",
                 "note": "Browse reviews and ratings for attractions"},
                {"name": "Google Maps", "url": f"https://www.google.com/maps/search/{cat_terms.split()[0]}+{location.replace(' ', '+')}",
                 "note": "Discover nearby attractions on the map"},
                {"name": "Viator", "url": f"https://www.viator.com/searchResults/all?text={location.replace(' ', '+')}",
                 "note": "Book tours and activities"},
            ]

            return {
                "results": results,
                "total": len(results),
                "discovery_platforms": platforms,
                "search_query": search_query,
                "search_metadata": {
                    "location": location,
                    "category": category,
                    "date": date,
                },
                "guidance": (
                    "Present attractions and activities from the search results. "
                    "Show name, description, rating, ticket price (if found), hours, and link. "
                    "ONLY quote prices and hours from the results — NEVER guess. "
                    "Also show the discovery platform links for more options. "
                    "Make recommendations based on the user's interests."
                ),
            }
        except Exception as e:
            return {"error": str(e), "search_query": search_query}

    return [
        search_web,
        search_accommodations,
        search_attractions,
    ]
