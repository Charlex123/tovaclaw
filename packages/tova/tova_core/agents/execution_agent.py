"""
Execution Agent — Intelligent order fulfillment with error recovery.

Called by the scheduler when an order is due for execution. Handles:
- Out-of-stock scenarios by finding alternatives
- Drug safety verification
- Intelligent error recovery with retry logic
"""

import logging

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tova_core.llm import build_llm
from tova_core.prompts.default import EXECUTION_AGENT_SYSTEM_PROMPT
from tova_core.providers.backend import BaseBackend
from tova_core.providers.store import BaseStore
from tova_core.tools.registry import build_execution_tools

logger = logging.getLogger(__name__)


async def run_execution_agent(
    order_id: str,
    auth_token: str,
    backend: BaseBackend,
    store: BaseStore,
    system_prompt: str | None = None,
) -> dict:
    """
    Execute an order intelligently.

    Args:
        order_id: The order ID to execute
        auth_token: Auth token for backend API calls
        backend: Your backend provider
        store: Your data store provider
        system_prompt: Custom system prompt (uses default if None)

    Returns:
        dict with: success, message, tools_used, alternatives_found
    """
    # Load order data
    order_data = await store.get_order(order_id)
    if not order_data:
        return {
            "success": False,
            "message": f"Order {order_id} not found",
            "tools_used": [],
        }

    user_id = order_data.get("user_id", "")
    item_name = order_data.get("item_name", "Unknown item")
    order_type = order_data.get("type", order_data.get("order_type", "product"))
    cost = order_data.get("cost", 0)

    execution_prompt = f"""Execute this order:

Order ID: {order_id}
User ID: {user_id}
Auth Token: {auth_token}
Type: {order_type}
Item: {item_name}
Item ID: {order_data.get("item_id", "")}
Quantity: {order_data.get("quantity", 1)}
Delivery Address: {order_data.get("delivery_address", "N/A")}
Cost: {cost}

Steps:
1. If this is a medication — run check_drug_safety on "{item_name}"
2. Check balance for user {user_id} with required amount {cost}
3. If balance insufficient, report the shortfall and STOP
4. If drug safety flagged, report the concern and STOP
5. Call execute_order with user_id="{user_id}" and order_id="{order_id}"
6. If execution fails, search for alternatives and report findings"""

    # Build tools and agent
    tools = build_execution_tools(backend, store)
    prompt = system_prompt or EXECUTION_AGENT_SYSTEM_PROMPT
    checkpointer = MemorySaver()
    llm = build_llm(temperature=0.1)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )

    thread_id = f"exec_{order_id}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = await agent.ainvoke(
            {"messages": [("human", execution_prompt)]},
            config=config,
        )

        ai_messages = [m for m in result["messages"] if m.type == "ai" and m.content]
        message = ai_messages[-1].content if ai_messages else "Execution completed."

        tool_messages = [m for m in result["messages"] if m.type == "tool"]
        tools_used = list({m.name for m in tool_messages})

        success = "execute_order" in tools_used and "error" not in message.lower()

        return {
            "success": success,
            "message": message,
            "tools_used": tools_used,
            "alternatives_found": "search_products" in tools_used or "search_services" in tools_used,
        }

    except Exception as e:
        logger.error(f"Execution agent error for order {order_id}: {e}")
        error_str = str(e).lower()
        if "credit balance" in error_str or "insufficient_quota" in error_str:
            message = "Service temporarily unavailable. Will retry later."
        else:
            message = f"Execution failed: {str(e)}"
        return {
            "success": False,
            "message": message,
            "tools_used": [],
        }
