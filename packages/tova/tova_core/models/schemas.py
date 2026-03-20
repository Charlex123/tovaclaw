"""Pydantic models for API requests/responses and agent state."""

from __future__ import annotations
from pydantic import BaseModel, Field


# ── API Request / Response ───────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    metadata: dict | None = None


class ChatResponse(BaseModel):
    """Response from the agent chat endpoint.

    The `action` field tells the client what type of response this is,
    and `data` contains structured results for rich UI rendering.

    Action types and their data:
    - "product_results"       -> data.results: [{id, name, price, store_name, distance, ...}]
    - "service_results"       -> data.results: [{id, name, price, provider_name, distance, ...}]
    - "practitioner_results"  -> data.results: [{schedule_id, name, specialty, available_slots, ...}]
    - "order_created"         -> data: {success, id, ...}
    - "order_cancelled"       -> data: {success, message}
    - "order_executed"        -> data: {success, message}
    - "appointment_booked"    -> data: {success, appointment_id, message}
    - "appointment_cancelled" -> data: {success, message}
    - "order_history"         -> data.orders: [{id, status, item_name, ...}]
    - "appointment_history"   -> data.appointments: [{id, type, name, status, ...}]
    - "balance_check"         -> data: {balance, currency, sufficient?, shortfall?}
    - "drug_safety"           -> data: {drug_name, safe, warnings}
    - "confirmation_needed"   -> data: null (reply contains confirmation prompt)
    - "info_needed"           -> data: null (reply contains question)
    - "error"                 -> data: null (reply contains error message)
    """
    reply: str
    action: str | None = None
    data: dict | None = None
    conversation_id: str
    tools_used: list[str] = []


class ExecuteRequest(BaseModel):
    order_id: str


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "tova"
    version: str = "0.1.0"


# ── Agent State (LangGraph) ─────────────────────────────────


class OrderAgentState(BaseModel):
    """State that flows through the Order Agent graph."""

    # Conversation
    messages: list[dict] = []
    user_id: str = ""
    conversation_id: str = ""
    auth_token: str = ""

    # Gathered context
    user_profile: dict | None = None
    selected_item: dict | None = None
    selected_service: dict | None = None
    delivery_address: str = ""
    delivery_fee: float = 0.0
    balance: float = 0.0

    # Order params
    order_type: str | None = None  # e.g., "product", "service"
    quantity: int = 1
    scheduled_date: str = ""
    schedule_type: str = "once"  # "once" or "recurring"
    duration: str | None = None
    frequency: str | None = None
    additional_info: str = ""

    # Recipient (ordering for someone else)
    is_for_someone_else: bool = False
    recipient_name: str = ""
    recipient_phone: str = ""

    # Appointment params
    selected_schedule: dict | None = None
    selected_slot: dict | None = None
    appointment_type: str | None = None  # e.g., "doctor", "nurse"
    professional_name: str = ""
    specialty: str = ""
    reason_for_booking: str = ""
    user_address: str = ""

    # Execution tracking
    tools_used: list[str] = []
    action: str | None = None
    order_result: dict | None = None
    error: str | None = None
    iteration_count: int = 0


class ExecutionAgentState(BaseModel):
    """State for the Execution Agent that handles intelligent order fulfillment."""

    messages: list[dict] = []
    user_id: str = ""
    auth_token: str = ""
    order_id: str = ""

    # The order being executed
    order_data: dict | None = None

    # Execution tracking
    step: str = "start"
    tools_used: list[str] = []
    error: str | None = None
    result: dict | None = None
    retry_count: int = 0
    alternatives_checked: bool = False
