"""
Order Agent — LangGraph stateful workflow for conversational order management.

This is the main patient-facing agent. It handles:
- Natural language order creation
- Reorder suggestions from history
- Order status checks
- Order cancellations
- Intelligent cost calculations

Uses LangGraph's prebuilt ReAct agent with checkpointing.
"""

import json
import logging
from datetime import datetime

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tova_core.llm import build_llm
from tova_core.prompts.default import ORDER_AGENT_SYSTEM_PROMPT
from tova_core.providers.backend import BaseBackend
from tova_core.providers.store import BaseStore
from tova_core.providers.notifier import BaseNotifier
from tova_core.tools.registry import build_order_tools

logger = logging.getLogger(__name__)

# Maps tool names to action types for client UI rendering
TOOL_ACTION_MAP = {
    "search_products": "product_results",
    "search_services": "service_results",
    "search_practitioners": "practitioner_results",
    "get_order_history": "order_history",
    "get_appointment_history": "appointment_history",
    "check_balance": "balance_check",
    "get_user_profile": "user_profile",
    "check_drug_safety": "drug_safety",
    "validate_prescription": "prescription_validated",
    "get_specialties_list": "specialties_list",
    "create_order": "order_created",
    "cancel_order": "order_cancelled",
    "execute_order": "order_executed",
    "verify_identity": "identity_verified",
    "book_appointment": "appointment_booked",
    "cancel_appointment": "appointment_cancelled",
    "calculate_delivery_fee": "delivery_fee",
}


def _extract_structured_data(messages: list) -> dict | None:
    """Extract the last meaningful tool result as structured data for the client."""
    tool_messages = [m for m in messages if m.type == "tool"]
    if not tool_messages:
        return None

    for msg in reversed(tool_messages):
        data_type = TOOL_ACTION_MAP.get(msg.name)
        if not data_type:
            continue

        try:
            if isinstance(msg.content, str):
                content = json.loads(msg.content)
            elif isinstance(msg.content, dict):
                content = msg.content
            else:
                continue
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(content, dict) and content.get("found") is False and not content.get("results"):
            continue

        return {"type": data_type, "tool": msg.name, **content}

    return None


def _determine_action(tools_used: list[str], reply: str) -> str | None:
    """Determine the action type from the tools used and reply content."""
    reply_lower = reply.lower()

    # Insufficient balance
    if "insufficient" in reply_lower or "top up" in reply_lower or "shortfall" in reply_lower:
        if any(t in tools_used for t in ["check_balance", "book_appointment", "create_order"]):
            return "insufficient_balance"

    # Write actions
    if "create_order" in tools_used:
        return "order_created"
    if "cancel_order" in tools_used:
        return "order_cancelled"
    if "execute_order" in tools_used:
        return "order_executed"
    if "book_appointment" in tools_used:
        return "appointment_booked"
    if "cancel_appointment" in tools_used:
        return "appointment_cancelled"

    # Search actions
    if "search_products" in tools_used:
        return "product_results"
    if "search_services" in tools_used:
        return "service_results"
    if "search_practitioners" in tools_used:
        return "practitioner_results"

    # Read actions
    if "get_order_history" in tools_used:
        return "order_history"
    if "get_appointment_history" in tools_used:
        return "appointment_history"
    if "check_balance" in tools_used:
        return "balance_check"
    if "check_drug_safety" in tools_used:
        return "drug_safety"

    # Conversational
    if any(q in reply_lower for q in ["confirm", "proceed", "shall i", "would you like me to"]):
        return "confirmation_needed"
    if "?" in reply:
        return "info_needed"
    return None


async def run_order_agent(
    user_id: str,
    user_message: str,
    auth_token: str,
    backend: BaseBackend,
    store: BaseStore,
    notifier: BaseNotifier | None = None,
    conversation_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    system_prompt: str | None = None,
) -> dict:
    """
    Run the order agent for a single user turn.

    Args:
        user_id: User ID
        user_message: The patient's message
        auth_token: Auth token for backend API calls
        backend: Your backend provider
        store: Your data store provider
        notifier: Optional notification provider
        conversation_id: Thread ID for conversation continuity
        latitude: User's latitude for proximity search
        longitude: User's longitude for proximity search
        system_prompt: Custom system prompt (uses default if None)

    Returns:
        dict with: reply, action, conversation_id, tools_used, data
    """
    is_new = not conversation_id
    if not conversation_id:
        conversation_id = await store.generate_id()

    # Build tools with the provided providers
    tools = build_order_tools(backend, store, notifier)

    # Build agent
    prompt = system_prompt or ORDER_AGENT_SYSTEM_PROMPT
    checkpointer = MemorySaver()
    llm = build_llm()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )

    # Inject context
    location_ctx = ""
    if latitude is not None and longitude is not None:
        location_ctx = f", latitude={latitude}, longitude={longitude}"

    pending_ctx = ""
    if is_new:
        try:
            pending = await store.get_pending_conversation(user_id)
            if pending:
                pending_ctx = (
                    f"\n[PENDING_CONVERSATION: User has an unfulfilled request. "
                    f"Title: \"{pending.get('title', '')}\", "
                    f"Last action: {pending.get('last_action', '')}, "
                    f"Last message: \"{pending.get('last_message', '')}...\". "
                    f"Mention this and ask if they want to continue or start new.]"
                )
        except Exception as e:
            logger.warning(f"Failed to check pending conversations: {e}")

    augmented = (
        f"[CONTEXT: user_id={user_id}, auth_token={auth_token}{location_ctx}]\n\n"
        f"{user_message}{pending_ctx}"
    )

    config = {"configurable": {"thread_id": conversation_id}}

    try:
        result = await agent.ainvoke(
            {"messages": [("human", augmented)]},
            config=config,
        )
    except Exception as e:
        if "INVALID_CHAT_HISTORY" in str(e) or "tool_calls" in str(e):
            logger.warning(f"Corrupted history for {user_id}, starting fresh.")
            conversation_id = await store.generate_id()
            config = {"configurable": {"thread_id": conversation_id}}
            try:
                result = await agent.ainvoke(
                    {"messages": [("human", augmented)]},
                    config=config,
                )
            except Exception as retry_err:
                logger.error(f"Agent retry failed: {retry_err}")
                return _error_response(conversation_id, str(retry_err))
        else:
            logger.error(f"Agent error for {user_id}: {e}")
            return _error_response(conversation_id, str(e))

    try:
        ai_messages = [m for m in result["messages"] if m.type == "ai" and m.content]
        reply = ai_messages[-1].content if ai_messages else "I completed the task."

        tool_messages = [m for m in result["messages"] if m.type == "tool"]
        tools_used = list({m.name for m in tool_messages})

        action = _determine_action(tools_used, reply)
        data = _extract_structured_data(result["messages"])

        # Persist conversation
        now = datetime.now().isoformat()
        conversation_messages = [
            {"role": "user", "content": user_message, "timestamp": now},
            {"role": "assistant", "content": reply, "action": action, "data": data, "timestamp": now},
        ]
        try:
            await store.save_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                messages=conversation_messages,
                title=user_message[:80],
            )
        except Exception as save_err:
            logger.warning(f"Failed to save conversation: {save_err}")

        return {
            "reply": reply,
            "action": action,
            "conversation_id": conversation_id,
            "tools_used": tools_used,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Response extraction error: {e}")
        return _error_response(conversation_id, str(e))


def _error_response(conversation_id: str, error: str) -> dict:
    error_lower = error.lower()
    if "credit balance" in error_lower or "insufficient_quota" in error_lower or "rate_limit" in error_lower:
        reply = "I'm temporarily unavailable. Please try again later."
    else:
        reply = "I'm sorry, something went wrong. Please try again."
    return {
        "reply": reply,
        "action": "error",
        "conversation_id": conversation_id,
        "tools_used": [],
        "data": None,
    }
