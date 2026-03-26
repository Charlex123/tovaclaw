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
    # Medical AI Chat
    "medical_chat": "medical_chat_response",
    "get_medical_profile": "medical_profile",
    "analyze_medical_records": "medical_records_analysis",
    "analyze_prescriptions": "prescription_analysis",
    "analyze_lab_results": "lab_results_analysis",
    "check_analysis_status": "analysis_status",
    "get_medical_conversations": "medical_conversations",
    "blood_group_chat": "blood_group_response",
    "analyze_appointment_chats": "appointment_chat_analysis",
    "send_medical_chat_email": "medical_email_sent",
    # Travel
    "search_flights": "flight_results",
    "search_trains": "train_results",
    "search_buses": "bus_results",
    "search_car_hire": "car_hire_results",
    "compare_transport": "transport_comparison",
    "find_nearest_airport": "nearest_airports",
    "resolve_airport": "airport_resolved",
    "save_travel_plan": "travel_plan_saved",
    # Web Search & Lifestyle
    "search_web": "web_search_results",
    "search_accommodations": "accommodation_results",
    "search_attractions": "attraction_results",
    # Workspace
    "create_file": "file_created",
    "write_to_file": "file_written",
    "read_file": "file_read",
    "analyze_document": "document_analysis",
    "generate_report": "report_generated",
    "generate_spreadsheet": "spreadsheet_generated",
    # Documents (Office & PDF)
    "read_office_document": "document_read",
    "create_word_document": "word_created",
    "create_excel_spreadsheet": "excel_created",
    "create_presentation": "presentation_created",
    "create_pdf_document": "pdf_created",
    "edit_office_document": "document_edited",
    # Smart Agent Factory
    "create_smart_agent": "smart_agent_created",
    "list_agent_templates": "agent_templates_listed",
    "deploy_agent_template": "agent_template_deployed",
    "customize_agent": "agent_customized",
    "create_agent_for_user": "agent_created",
    "list_user_agents": "user_agents_listed",
    # Creative (Image, Video, Audio)
    "generate_image": "image_generated",
    "edit_image": "image_edited",
    "generate_video": "video_generated",
    "check_video_status": "video_status",
    "image_to_video": "video_from_image",
    "text_to_speech": "speech_generated",
    "list_voices": "voices_listed",
    # Workforce
    "create_workforce_agent": "agent_created",
    "setup_workflow": "workflow_deployed",
    "delegate_task": "task_delegated",
    "run_workflow": "workflow_executed",
    "list_workforce": "workforce_listed",
    "monitor_workforce": "workforce_status",
    "list_workflow_templates": "templates_listed",
    "add_agent_to_workflow": "workflow_agent_added",
    "remove_workflow_step": "workflow_step_removed",
    "reorder_workflow": "workflow_reordered",
    # Code Execution
    "execute_code": "code_executed",
    "run_shell_command": "shell_executed",
    "read_project_file": "project_file_read",
    "write_project_file": "project_file_written",
    "edit_project_file": "project_file_edited",
    "search_codebase": "codebase_searched",
    "list_project_files": "project_files_listed",
    "git_command": "git_executed",
    # Model Management
    "check_model_status": "model_status",
    "install_model": "model_installed",
    "recommend_models": "model_recommendations",
    "list_available_models": "models_listed",
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

    # Medical AI Chat actions
    if "medical_chat" in tools_used:
        return "medical_chat_response"
    if "get_medical_profile" in tools_used:
        return "medical_profile"
    if "analyze_medical_records" in tools_used:
        return "medical_records_analysis"
    if "analyze_prescriptions" in tools_used:
        return "prescription_analysis"
    if "analyze_lab_results" in tools_used:
        return "lab_results_analysis"
    if "check_analysis_status" in tools_used:
        return "analysis_status"
    if "blood_group_chat" in tools_used:
        return "blood_group_response"
    if "analyze_appointment_chats" in tools_used:
        return "appointment_chat_analysis"
    if "send_medical_chat_email" in tools_used:
        return "medical_email_sent"
    if "get_medical_conversations" in tools_used:
        return "medical_conversations"

    # Read actions
    if "get_order_history" in tools_used:
        return "order_history"
    if "get_appointment_history" in tools_used:
        return "appointment_history"
    if "check_balance" in tools_used:
        return "balance_check"
    if "check_drug_safety" in tools_used:
        return "drug_safety"

    # Travel actions
    if "search_flights" in tools_used:
        return "flight_results"
    if "search_trains" in tools_used:
        return "train_results"
    if "search_buses" in tools_used:
        return "bus_results"
    if "compare_transport" in tools_used:
        return "transport_comparison"
    if "save_travel_plan" in tools_used:
        return "travel_plan_saved"

    # Web search & lifestyle actions
    if "search_accommodations" in tools_used:
        return "accommodation_results"
    if "search_attractions" in tools_used:
        return "attraction_results"
    if "search_web" in tools_used:
        return "web_search_results"

    # Smart Agent Factory actions
    if "create_smart_agent" in tools_used:
        return "smart_agent_created"
    if "list_agent_templates" in tools_used:
        return "agent_templates_listed"
    if "deploy_agent_template" in tools_used:
        return "agent_template_deployed"
    if "customize_agent" in tools_used:
        return "agent_customized"
    if "create_agent_for_user" in tools_used:
        return "agent_created"
    if "list_user_agents" in tools_used:
        return "user_agents_listed"

    # Creative actions (Image, Video, Audio)
    if "generate_image" in tools_used:
        return "image_generated"
    if "edit_image" in tools_used:
        return "image_edited"
    if "generate_video" in tools_used:
        return "video_generated"
    if "check_video_status" in tools_used:
        return "video_status"
    if "image_to_video" in tools_used:
        return "video_from_image"
    if "text_to_speech" in tools_used:
        return "speech_generated"

    # Document actions (Office & PDF)
    if "read_office_document" in tools_used:
        return "document_read"
    if "create_word_document" in tools_used:
        return "word_created"
    if "create_excel_spreadsheet" in tools_used:
        return "excel_created"
    if "create_presentation" in tools_used:
        return "presentation_created"
    if "create_pdf_document" in tools_used:
        return "pdf_created"
    if "edit_office_document" in tools_used:
        return "document_edited"

    # Workspace actions
    if "create_file" in tools_used:
        return "file_created"
    if "analyze_document" in tools_used:
        return "document_analysis"
    if "generate_report" in tools_used:
        return "report_generated"
    if "generate_spreadsheet" in tools_used:
        return "spreadsheet_generated"

    # Workforce actions
    if "create_workforce_agent" in tools_used:
        return "agent_created"
    if "setup_workflow" in tools_used:
        return "workflow_deployed"
    if "delegate_task" in tools_used:
        return "task_delegated"
    if "run_workflow" in tools_used:
        return "workflow_executed"
    if "list_workforce" in tools_used:
        return "workforce_listed"
    if "monitor_workforce" in tools_used:
        return "workforce_status"
    if "add_agent_to_workflow" in tools_used:
        return "workflow_agent_added"
    if "remove_workflow_step" in tools_used:
        return "workflow_step_removed"
    if "reorder_workflow" in tools_used:
        return "workflow_reordered"

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
    extra_tools: list | None = None,
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
        extra_tools: Additional tools to include (travel, web search, etc.)

    Returns:
        dict with: reply, action, conversation_id, tools_used, data
    """
    is_new = not conversation_id
    if not conversation_id:
        conversation_id = await store.generate_id()

    # Build tools with the provided providers
    tools = build_order_tools(backend, store, notifier)

    # Add extra tools (travel, web search, accommodations, etc.)
    if extra_tools:
        tools.extend(extra_tools)

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
