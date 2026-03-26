"""
Phone call and SMS tools.

Enable agents to make automated phone calls and send SMS messages.
"""

from __future__ import annotations

import logging
from langchain_core.tools import tool

from tova_core.providers.telephony import BaseTelephony

logger = logging.getLogger(__name__)


def build_phone_tools(telephony: BaseTelephony) -> list:
    """Build phone call/SMS tools using the provider pattern."""

    @tool
    async def make_phone_call(
        to_number: str,
        message: str,
        priority: str = "normal",
    ) -> dict:
        """Make an automated phone call with text-to-speech.

        Args:
            to_number: Phone number to call (E.164 format: +1234567890)
            message: Message to speak via TTS
            priority: Call priority: normal, high, critical
        """
        try:
            result = await telephony.make_call(
                to_number=to_number,
                message=message,
                priority=priority,
            )
            return {
                "success": True,
                "call_id": result.get("call_id", ""),
                "status": result.get("status", ""),
                "to": to_number,
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def check_call_status(call_id: str) -> dict:
        """Check the status of a previously initiated phone call.

        Args:
            call_id: The call ID returned from make_phone_call
        """
        try:
            result = await telephony.get_call_status(call_id)
            return {
                "call_id": call_id,
                "status": result.get("status", "unknown"),
                "duration": result.get("duration", 0),
                "answered": result.get("answered", False),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def send_sms(
        to_number: str,
        message: str,
    ) -> dict:
        """Send an SMS text message.

        Args:
            to_number: Phone number (E.164 format: +1234567890)
            message: SMS text (keep under 160 characters for single SMS)
        """
        try:
            result = await telephony.send_sms(
                to_number=to_number,
                message=message,
            )
            return {
                "success": True,
                "message_id": result.get("message_id", ""),
                "status": result.get("status", ""),
                "to": to_number,
            }
        except NotImplementedError:
            return {"error": "SMS not supported by telephony provider"}
        except Exception as e:
            return {"error": str(e)}

    return [make_phone_call, check_call_status, send_sms]
