"""
Tool registry — builds LangGraph tools from provider instances.

Instead of hardcoded Firestore/BackendClient calls, each tool uses the
abstract providers (BaseBackend, BaseStore, BaseNotifier) that you implement.

Usage:
    backend = MyBackend(auth_token="...")
    store = MyStore()
    notifier = MyNotifier()

    order_tools = build_order_tools(backend, store, notifier)
    execution_tools = build_execution_tools(backend, store)
"""

import logging
from langchain_core.tools import tool

from tova_core.providers.backend import BaseBackend
from tova_core.providers.store import BaseStore
from tova_core.providers.notifier import BaseNotifier
from tova_core.tools.helpers import (
    filter_by_radius,
    suggest_next_radius,
    is_future_date,
    safe_timestamp,
)

logger = logging.getLogger(__name__)


def build_order_tools(
    backend: BaseBackend,
    store: BaseStore,
    notifier: BaseNotifier | None = None,
) -> list:
    """Build the full set of tools for the patient-facing Order Agent.

    Args:
        backend: Your backend provider implementation
        store: Your data store provider implementation
        notifier: Optional notification provider
    """

    @tool
    async def search_products(
        query: str,
        latitude: float = 0,
        longitude: float = 0,
        search_radius_km: float = 0,
        alternative_queries: str = "",
    ) -> dict:
        """Search for products (medicines, medical devices, supplies) available in nearby stores.
        Results are sorted by proximity when latitude/longitude are provided.

        SMART SEARCH: If initial search returns no results, try:
        1. Generic name variants (e.g., "paracetamol" if "Panadol" not found)
        2. Broader category search
        3. Expand search_radius_km progressively: 5 -> 10 -> 20 -> 35 -> 50 km

        Args:
            query: Product name to search for
            latitude: User's latitude for proximity-based results
            longitude: User's longitude for proximity-based results
            search_radius_km: Max distance in km (0 = no limit)
            alternative_queries: Comma-separated alternative search terms to try if primary fails
        """
        queries_to_try = [query]
        if alternative_queries:
            queries_to_try.extend([q.strip() for q in alternative_queries.split(",") if q.strip()])

        all_results = []
        tried_queries = []

        for q in queries_to_try:
            tried_queries.append(q)

            try:
                items = await backend.search_products(
                    query=q, latitude=latitude, longitude=longitude,
                )
                if search_radius_km > 0 and items and latitude and longitude:
                    items = filter_by_radius(items, latitude, longitude, search_radius_km)

                for item in (items or [])[:8]:
                    price = item.get("price", item.get("pricePerUnit", 0))
                    discount = item.get("discount", 0)
                    final = price - (price * discount / 100) if discount else price
                    all_results.append({
                        "id": item.get("id", ""),
                        "name": item.get("name", "Unknown"),
                        "price": price,
                        "discount": discount,
                        "final_price": round(final, 2),
                        "store_id": item.get("store_id", item.get("storeId", "")),
                        "store_name": item.get("store_name", item.get("storeName", "")),
                        "in_stock": item.get("in_stock", item.get("inStock", True)),
                        "category": item.get("category", ""),
                        "description": item.get("description", ""),
                        "distance_km": item.get("distance_km", item.get("distanceFromUser", "")),
                        "prescription_required": item.get("prescription_required", item.get("prescriptionRequired", "")),
                        "matched_query": q,
                    })
            except NotImplementedError:
                # Try store fallback
                try:
                    items = await store.search_products(q, limit=8)
                    for item in (items or [])[:5]:
                        all_results.append({
                            "id": item.get("id", ""),
                            "name": item.get("name", "Unknown"),
                            "price": item.get("price", 0),
                            "store_name": item.get("store_name", ""),
                            "in_stock": item.get("in_stock", True),
                            "matched_query": q,
                        })
                except NotImplementedError:
                    pass
            except Exception as e:
                logger.warning(f"Product search failed for '{q}': {e}")

            if all_results:
                break

        # Deduplicate
        seen = set()
        unique = []
        for r in all_results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        if not unique:
            next_radius = suggest_next_radius(search_radius_km) if search_radius_km > 0 else 5
            return {
                "found": False,
                "message": f'No products found for "{query}".',
                "results": [],
                "tried_queries": tried_queries,
                "searched_radius_km": search_radius_km if search_radius_km > 0 else "unlimited",
                "suggestion": f"Try expanding search to {next_radius} km" if next_radius else "No more areas to expand",
                "next_radius_km": next_radius,
            }

        return {
            "found": True,
            "count": len(unique),
            "results": unique[:5],
            "proximity": bool(latitude and longitude),
            "searched_radius_km": search_radius_km if search_radius_km > 0 else "unlimited",
            "tried_queries": tried_queries,
        }

    @tool
    async def search_services(
        query: str,
        latitude: float = 0,
        longitude: float = 0,
        search_radius_km: float = 0,
        alternative_queries: str = "",
    ) -> dict:
        """Search for services (lab tests, diagnostics, screenings) available nearby.

        Args:
            query: Service name to search for
            latitude: User's latitude for proximity results
            longitude: User's longitude for proximity results
            search_radius_km: Max distance in km (0 = no limit)
            alternative_queries: Comma-separated alternative search terms
        """
        queries_to_try = [query]
        if alternative_queries:
            queries_to_try.extend([q.strip() for q in alternative_queries.split(",") if q.strip()])

        all_results = []
        tried_queries = []

        for q in queries_to_try:
            tried_queries.append(q)
            try:
                items = await backend.search_services(
                    query=q, latitude=latitude, longitude=longitude,
                )
                if search_radius_km > 0 and items and latitude and longitude:
                    items = filter_by_radius(items, latitude, longitude, search_radius_km)

                for item in (items or [])[:8]:
                    price = item.get("price", 0)
                    discount = item.get("discount", 0)
                    final = price - (price * discount / 100) if discount else price
                    all_results.append({
                        "id": item.get("id", ""),
                        "name": item.get("name", "Unknown"),
                        "price": price,
                        "final_price": round(final, 2),
                        "provider_id": item.get("provider_id", ""),
                        "provider_name": item.get("provider_name", ""),
                        "category": item.get("category", ""),
                        "description": item.get("description", ""),
                        "distance_km": item.get("distance_km", ""),
                        "matched_query": q,
                    })
            except NotImplementedError:
                try:
                    items = await store.search_services(q, limit=8)
                    for item in (items or [])[:5]:
                        all_results.append({
                            "id": item.get("id", ""),
                            "name": item.get("name", "Unknown"),
                            "price": item.get("price", 0),
                            "provider_name": item.get("provider_name", ""),
                            "matched_query": q,
                        })
                except NotImplementedError:
                    pass
            except Exception as e:
                logger.warning(f"Service search failed for '{q}': {e}")

            if all_results:
                break

        seen = set()
        unique = []
        for r in all_results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        if not unique:
            next_radius = suggest_next_radius(search_radius_km) if search_radius_km > 0 else 5
            return {
                "found": False,
                "message": f'No services found for "{query}".',
                "results": [],
                "tried_queries": tried_queries,
                "searched_radius_km": search_radius_km if search_radius_km > 0 else "unlimited",
                "next_radius_km": next_radius,
            }

        return {
            "found": True,
            "count": len(unique),
            "results": unique[:5],
            "proximity": bool(latitude and longitude),
            "tried_queries": tried_queries,
        }

    @tool
    async def check_balance(user_id: str, required_amount: float = 0) -> dict:
        """Check the user's wallet/payment balance. Call before creating an order
        to verify the user has enough funds.
        """
        wallet = await store.get_balance(user_id)
        balance = wallet.get("balance", 0)
        currency = wallet.get("currency", "USD")

        result = {"balance": balance, "currency": currency}
        if required_amount > 0:
            result["required_amount"] = required_amount
            result["sufficient"] = balance >= required_amount
            result["shortfall"] = max(0, required_amount - balance)
        return result

    @tool
    async def get_user_profile(user_id: str, include_order_history: bool = False) -> dict:
        """Get the user's profile info including name, address, and optionally
        their recent order history for reorder suggestions.
        """
        user = await store.get_user(user_id)
        if not user:
            return {"error": "User not found"}

        profile = {
            "name": user.get("name", user.get("fullName", "User")),
            "email": user.get("email"),
            "phone": user.get("phone", user.get("phoneNumber")),
            "address": user.get("address"),
        }

        if include_order_history:
            orders = await store.get_orders(user_id, limit=10)
            profile["recent_orders"] = [
                {
                    "id": o.get("id"),
                    "type": o.get("type", o.get("order_type")),
                    "status": o.get("status"),
                    "item_name": o.get("item_name"),
                    "scheduled_date": o.get("scheduled_date"),
                    "cost": o.get("cost"),
                    "delivery_address": o.get("delivery_address"),
                }
                for o in orders
            ]

        return profile

    @tool
    async def get_order_history(
        user_id: str,
        status: str = "",
        order_type: str = "",
    ) -> dict:
        """Get the user's order history. Filter by status or order_type."""
        orders = await store.get_orders(
            user_id,
            status=status or None,
            order_type=order_type or None,
            limit=10,
        )
        if not orders:
            return {"found": False, "message": "No orders found.", "orders": []}

        return {
            "found": True,
            "count": len(orders),
            "orders": [
                {
                    "id": o.get("id"),
                    "type": o.get("type", o.get("order_type")),
                    "status": o.get("status"),
                    "item_name": o.get("item_name"),
                    "quantity": o.get("quantity", 1),
                    "scheduled_date": o.get("scheduled_date"),
                    "delivery_address": o.get("delivery_address"),
                    "cost": o.get("cost"),
                    "schedule_type": o.get("schedule_type"),
                    "frequency": o.get("frequency"),
                    "created_at": str(o.get("created_at", "")),
                }
                for o in orders
            ],
        }

    @tool
    async def check_drug_safety(drug_name: str) -> dict:
        """Check a medication for safety concerns including recalls and known
        adverse effects. Call this before creating an order for medications.
        """
        result = await store.check_drug_safety(drug_name)
        return {
            "drug_name": drug_name,
            "safe_to_order": result.get("safe", True),
            "warnings": result.get("warnings", []),
            "message": result.get("message", f"No safety concerns found for {drug_name}."),
        }

    @tool
    async def search_practitioners(
        practitioner_type: str = "doctor",
        specialty: str = "",
        query: str = "",
        alternative_specialties: str = "",
        latitude: float = 0,
        longitude: float = 0,
    ) -> dict:
        """Search for available healthcare practitioners (doctors, nurses, etc.).
        Returns profiles with available time slots and fees.

        Args:
            practitioner_type: Type of practitioner (e.g., "doctor", "nurse")
            specialty: Specialty to filter by
            query: Name to search for
            alternative_specialties: Comma-separated fallback specialties
            latitude: User's latitude for proximity
            longitude: User's longitude for proximity
        """
        specialties_to_try = [specialty] if specialty else []
        if alternative_specialties:
            specialties_to_try.extend([s.strip() for s in alternative_specialties.split(",") if s.strip()])

        all_results = []
        tried = []

        for spec in (specialties_to_try or [""]):
            tried.append(spec or "(any)")
            try:
                schedules = await backend.search_practitioners(
                    practitioner_type=practitioner_type,
                    specialty=spec,
                    query=query,
                    latitude=latitude,
                    longitude=longitude,
                )
                for s in (schedules or [])[:5]:
                    slots = s.get("available_slots", [])
                    formatted = []
                    for slot in slots[:5]:
                        if not is_future_date(slot.get("date")):
                            continue
                        formatted.append({
                            "slot_id": slot.get("slot_id", slot.get("id")),
                            "date": safe_timestamp(slot.get("date")),
                            "start_time": safe_timestamp(slot.get("start_time", slot.get("startTime"))),
                            "end_time": safe_timestamp(slot.get("end_time", slot.get("endTime"))),
                            "amount": slot.get("amount", 0),
                        })
                    if not formatted:
                        continue
                    all_results.append({
                        "schedule_id": s.get("schedule_id", s.get("id", "")),
                        "professional_id": s.get("professional_id", ""),
                        "name": s.get("name", "Unknown"),
                        "specialty": s.get("specialty", ""),
                        "description": s.get("description", ""),
                        "rating": s.get("rating", 0),
                        "rating_count": s.get("rating_count", 0),
                        "avatar": s.get("avatar", ""),
                        "available_slots": formatted,
                        "total_available": len(formatted),
                        "matched_specialty": spec,
                        "practitioner_type": practitioner_type,
                    })
            except NotImplementedError:
                try:
                    schedules = await store.search_practitioners(
                        practitioner_type=practitioner_type,
                        specialty=spec,
                        query=query,
                        limit=8,
                    )
                    for s in (schedules or [])[:5]:
                        slots = s.get("available_slots", [])
                        formatted = [
                            {
                                "slot_id": sl.get("slot_id", sl.get("id")),
                                "date": safe_timestamp(sl.get("date")),
                                "start_time": safe_timestamp(sl.get("start_time")),
                                "end_time": safe_timestamp(sl.get("end_time")),
                                "amount": sl.get("amount", 0),
                            }
                            for sl in slots[:5]
                            if is_future_date(sl.get("date"))
                        ]
                        if formatted:
                            all_results.append({
                                "schedule_id": s.get("id", ""),
                                "professional_id": s.get("professional_id", ""),
                                "name": s.get("name", "Unknown"),
                                "specialty": s.get("specialty", ""),
                                "available_slots": formatted,
                                "total_available": len(formatted),
                                "matched_specialty": spec,
                                "practitioner_type": practitioner_type,
                            })
                except NotImplementedError:
                    pass
            except Exception as e:
                logger.warning(f"Practitioner search failed: {e}")

            if all_results:
                break

        if not all_results:
            return {
                "found": False,
                "message": f"No available {practitioner_type}s found.",
                "results": [],
                "tried_specialties": tried,
            }

        return {"found": True, "count": len(all_results), "results": all_results, "tried_specialties": tried}

    @tool
    async def get_specialties_list() -> dict:
        """Get all available practitioner specialties."""
        try:
            specialties = await store.get_practitioner_specialties()
            return {"specialties": specialties, "count": len(specialties)}
        except NotImplementedError:
            return {"specialties": [], "count": 0, "message": "Specialties list not available"}

    @tool
    async def get_appointment_history(
        user_id: str,
        appointment_type: str = "",
        status: str = "",
    ) -> dict:
        """Get the user's appointment history."""
        try:
            appointments = await store.get_appointments(
                user_id, appointment_type=appointment_type, status=status, limit=10
            )
        except NotImplementedError:
            return {"found": False, "message": "Appointment history not available.", "appointments": []}

        if not appointments:
            return {"found": False, "message": "No appointments found.", "appointments": []}

        return {
            "found": True,
            "count": len(appointments),
            "appointments": [
                {
                    "id": a.get("id"),
                    "type": a.get("type"),
                    "professional_name": a.get("professional_name", ""),
                    "specialty": a.get("specialty", ""),
                    "status": a.get("status", ""),
                    "date": str(a.get("date", "")),
                    "amount": a.get("amount", 0),
                }
                for a in appointments
            ],
        }

    @tool
    async def book_appointment(
        user_id: str,
        schedule_id: str,
        slot_id: str,
        professional_id: str,
        professional_name: str,
        appointment_type: str,
        specialty: str,
        amount: float,
        slot_date: str = "",
        slot_start_time: str = "",
        slot_end_time: str = "",
        notes: str = "",
        reason: str = "",
        user_address: str = "",
    ) -> dict:
        """Book an appointment with a practitioner. Only call after user confirmation.

        Args:
            user_id: The user's ID
            schedule_id: Schedule document ID
            slot_id: Time slot ID
            professional_id: Practitioner user ID
            professional_name: Practitioner name
            appointment_type: Type (e.g., "doctor", "nurse")
            specialty: Practitioner's specialty
            amount: Fee amount
            slot_date: Appointment date
            slot_start_time: Start time
            slot_end_time: End time
            notes: Patient notes
            reason: Reason for visit
            user_address: Required for home visit appointments
        """
        # Balance check
        wallet = await store.get_balance(user_id)
        balance = wallet.get("balance", 0)
        if balance < amount:
            shortfall = amount - balance
            currency = wallet.get("currency", "USD")
            return {
                "success": False,
                "error": f"Insufficient balance. You have {currency} {balance:,.0f} but need {currency} {amount:,.0f}. Shortfall: {currency} {shortfall:,.0f}.",
                "balance": balance,
                "required": amount,
                "shortfall": shortfall,
            }

        try:
            result = await backend.book_appointment({
                "schedule_id": schedule_id,
                "slot_id": slot_id,
                "professional_id": professional_id,
                "professional_name": professional_name,
                "appointment_type": appointment_type,
                "specialty": specialty,
                "amount": amount,
                "date": slot_date,
                "start_time": slot_start_time,
                "end_time": slot_end_time,
                "notes": notes,
                "reason": reason,
                "user_address": user_address,
                "user_id": user_id,
            })

            if notifier:
                await notifier.notify(
                    user_id=user_id,
                    title=f"{appointment_type.capitalize()} Appointment Booked",
                    body=f"Your appointment with {professional_name} ({specialty}) has been confirmed.",
                    data={"type": "appointment_booked", "appointment_type": appointment_type},
                )

            return {"success": True, "message": f"Appointment booked with {professional_name}!", **result}
        except NotImplementedError:
            return {"success": False, "error": "Appointment booking is not configured."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool
    async def cancel_appointment(
        user_id: str,
        appointment_id: str,
        reason: str = "",
    ) -> dict:
        """Cancel an existing appointment. Always confirm with the user first."""
        try:
            result = await backend.cancel_appointment(appointment_id, reason)

            if notifier:
                await notifier.notify(
                    user_id=user_id,
                    title="Appointment Cancelled",
                    body=f"Your appointment has been cancelled.{f' Reason: {reason}' if reason else ''}",
                    data={"type": "appointment_cancelled", "appointment_id": appointment_id},
                )

            return {"success": True, "message": "Appointment cancelled.", **result}
        except NotImplementedError:
            return {"success": False, "error": "Appointment cancellation is not configured."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool
    async def create_order(
        user_id: str,
        order_type: str,
        item_id: str,
        item_name: str,
        delivery_address: str,
        scheduled_date: str,
        cost: float,
        quantity: int = 1,
        schedule_type: str = "once",
        duration: str = "",
        frequency: str = "",
        delivery_fee: float = 0,
        additional_info: str = "",
        is_for_someone_else: bool = False,
        recipient_name: str = "",
        recipient_phone: str = "",
    ) -> dict:
        """Create a new order. This is the FINAL action — only call after user confirmation.

        Args:
            user_id: The user's ID
            order_type: Type of order (e.g., "product", "service")
            item_id: Product/service ID
            item_name: Product/service name
            delivery_address: Delivery address
            scheduled_date: ISO 8601 date
            cost: Total cost per execution
            quantity: Number of items
            schedule_type: "once" or "recurring"
            duration: For recurring (e.g., "1_month", "3_months")
            frequency: For recurring (e.g., "daily", "weekly", "monthly")
            delivery_fee: Delivery fee
            additional_info: Optional notes
            is_for_someone_else: True if ordering for another person
            recipient_name: Recipient's name
            recipient_phone: Recipient's phone
        """
        if is_for_someone_else and schedule_type == "recurring":
            return {"success": False, "error": "Recurring orders for someone else are not allowed."}

        if is_for_someone_else and (not recipient_name or not recipient_phone):
            return {"success": False, "error": "Recipient name and phone are required when ordering for someone else."}

        # Balance check
        wallet = await store.get_balance(user_id)
        balance = wallet.get("balance", 0)
        currency = wallet.get("currency", "USD")
        if balance < cost:
            shortfall = cost - balance
            return {
                "success": False,
                "error": f"Insufficient balance. You have {currency} {balance:,.0f} but need {currency} {cost:,.0f}.",
                "balance": balance,
                "required": cost,
                "shortfall": shortfall,
            }

        order_data = {
            "user_id": user_id,
            "order_type": order_type,
            "item_id": item_id,
            "item_name": item_name,
            "quantity": quantity,
            "delivery_address": delivery_address,
            "scheduled_date": scheduled_date,
            "cost": cost,
            "delivery_fee": delivery_fee,
            "schedule_type": schedule_type,
            "additional_info": additional_info,
        }

        if schedule_type == "recurring" and frequency:
            order_data["frequency"] = frequency
            order_data["duration"] = duration

        if is_for_someone_else:
            order_data["is_for_someone_else"] = True
            order_data["recipient_name"] = recipient_name
            order_data["recipient_phone"] = recipient_phone

        try:
            result = await backend.create_order(order_data)

            if notifier:
                await notifier.notify(
                    user_id=user_id,
                    title="Order Created",
                    body=f"Your order for {item_name} has been placed!",
                    data={"type": "order_created", "order_type": order_type},
                )

            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool
    async def execute_order(user_id: str, order_id: str) -> dict:
        """Execute an existing order immediately."""
        try:
            result = await backend.execute_order(order_id)

            if notifier:
                await notifier.notify(
                    user_id=user_id,
                    title="Order Executed",
                    body="Your order has been processed.",
                    data={"type": "order_executed", "order_id": order_id},
                )

            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool
    async def cancel_order(user_id: str, order_id: str, reason: str = "") -> dict:
        """Cancel an existing order. Always confirm with the user first."""
        try:
            result = await backend.cancel_order(order_id, reason)

            if notifier:
                await notifier.notify(
                    user_id=user_id,
                    title="Order Cancelled",
                    body=f"Your order has been cancelled.{f' Reason: {reason}' if reason else ''}",
                    data={"type": "order_cancelled", "order_id": order_id},
                )

            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool
    async def calculate_delivery_fee(
        item_type: str,
        store_id: str,
        delivery_address: str,
    ) -> dict:
        """Calculate delivery fee based on item type, store, and delivery address."""
        try:
            result = await backend.calculate_delivery_fee({
                "item_type": item_type,
                "store_id": store_id,
                "delivery_address": delivery_address,
            })
            return {"delivery_fee": result.get("fee", 0), "currency": result.get("currency", "USD")}
        except NotImplementedError:
            return {"delivery_fee": 0, "currency": "USD", "note": "Delivery fee calculation not configured"}
        except Exception:
            return {"delivery_fee": 0, "currency": "USD", "note": "Could not calculate, using default"}

    @tool
    async def validate_prescription(prescription_url: str) -> dict:
        """Validate an uploaded prescription document."""
        if not prescription_url:
            return {"valid": False, "error": "No prescription URL provided."}
        try:
            result = await backend.validate_prescription(prescription_url)
            return result
        except NotImplementedError:
            return {"valid": False, "error": "Prescription validation not configured."}
        except Exception as e:
            return {"valid": False, "error": f"Validation failed: {str(e)}"}

    @tool
    async def verify_identity(user_id: str, id_number: str, id_type: str = "", country: str = "") -> dict:
        """Verify a user's identity document (required for some services like home visits).

        Args:
            user_id: The user's ID
            id_number: The identity document number
            id_type: Type of ID (e.g., "NIN", "SSN", "passport")
            country: Country code
        """
        try:
            result = await backend.verify_identity({
                "user_id": user_id,
                "id_number": id_number,
                "id_type": id_type,
                "country": country,
            })
            return result
        except NotImplementedError:
            return {"verified": False, "error": "Identity verification not configured."}
        except Exception as e:
            return {"verified": False, "error": str(e)}

    # Build the tool lists
    order_tools = [
        search_products,
        search_services,
        search_practitioners,
        get_specialties_list,
        get_appointment_history,
        book_appointment,
        cancel_appointment,
        check_balance,
        get_user_profile,
        get_order_history,
        check_drug_safety,
        calculate_delivery_fee,
        validate_prescription,
        verify_identity,
        create_order,
        cancel_order,
    ]

    return order_tools


def build_execution_tools(
    backend: BaseBackend,
    store: BaseStore,
) -> list:
    """Build tools for the Execution Agent (scheduler-facing).

    These are a subset of order tools focused on fulfillment.
    """

    @tool
    async def search_products(
        query: str,
        latitude: float = 0,
        longitude: float = 0,
        search_radius_km: float = 0,
    ) -> dict:
        """Search for products — used to find alternatives when items are out of stock."""
        try:
            items = await backend.search_products(query=query, latitude=latitude, longitude=longitude)
            if search_radius_km > 0 and items and latitude and longitude:
                items = filter_by_radius(items, latitude, longitude, search_radius_km)
            results = [
                {"id": i.get("id", ""), "name": i.get("name", ""), "price": i.get("price", 0), "in_stock": i.get("in_stock", True)}
                for i in (items or [])[:5]
            ]
            return {"found": bool(results), "results": results}
        except Exception as e:
            return {"found": False, "error": str(e)}

    @tool
    async def search_services(query: str) -> dict:
        """Search for services — used to find alternatives."""
        try:
            items = await backend.search_services(query=query)
            results = [
                {"id": i.get("id", ""), "name": i.get("name", ""), "price": i.get("price", 0)}
                for i in (items or [])[:5]
            ]
            return {"found": bool(results), "results": results}
        except Exception as e:
            return {"found": False, "error": str(e)}

    @tool
    async def check_balance(user_id: str, required_amount: float = 0) -> dict:
        """Check wallet balance before executing an order."""
        wallet = await store.get_balance(user_id)
        balance = wallet.get("balance", 0)
        result = {"balance": balance, "currency": wallet.get("currency", "USD")}
        if required_amount > 0:
            result["sufficient"] = balance >= required_amount
            result["shortfall"] = max(0, required_amount - balance)
        return result

    @tool
    async def get_user_profile(user_id: str) -> dict:
        """Get user profile for execution context."""
        user = await store.get_user(user_id)
        if not user:
            return {"error": "User not found"}
        return {"name": user.get("name", "User"), "address": user.get("address")}

    @tool
    async def check_drug_safety(drug_name: str) -> dict:
        """Check drug safety before executing an order."""
        result = await store.check_drug_safety(drug_name)
        return {
            "drug_name": drug_name,
            "safe_to_order": result.get("safe", True),
            "warnings": result.get("warnings", []),
        }

    @tool
    async def execute_order(user_id: str, order_id: str) -> dict:
        """Execute an automated order."""
        try:
            result = await backend.execute_order(order_id)
            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return [
        search_products,
        search_services,
        check_balance,
        get_user_profile,
        check_drug_safety,
        execute_order,
    ]
