"""
Twilio telephony provider — phone calls and SMS.

Makes real phone calls with text-to-speech and sends SMS messages.
Used by the emergency escalation system and phone tools.

Usage:
    # From env vars (recommended):
    TWILIO_ACCOUNT_SID=AC...
    TWILIO_AUTH_TOKEN=...
    TWILIO_PHONE_NUMBER=+1234567890
    telephony = TwilioTelephony()

    # Explicit:
    telephony = TwilioTelephony(
        account_sid="AC...",
        auth_token="...",
        from_number="+1234567890",
    )

    # Make a call:
    result = await telephony.make_call("+1555123456", "Hello from Tova")

    # Send SMS:
    result = await telephony.send_sms("+1555123456", "Your order is ready")

Install: pip install tova[telephony]
"""

from __future__ import annotations

import logging
import os
from typing import Any

from tova_core.providers.telephony import BaseTelephony

logger = logging.getLogger(__name__)


class TwilioTelephony(BaseTelephony):
    """Twilio-backed telephony for calls and SMS.

    Supports:
    - Outbound calls with TTS (text-to-speech)
    - Call status tracking
    - SMS sending
    - Multiple voice options (man, woman, alice, Polly voices)
    - Priority-based call handling
    """

    # Twilio voice map
    VOICES = {
        "default": "Polly.Joanna",
        "man": "Polly.Matthew",
        "woman": "Polly.Joanna",
        "alice": "alice",
    }

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
        status_callback_url: str | None = None,
    ):
        self.account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = from_number or os.environ.get("TWILIO_PHONE_NUMBER", "")
        self.status_callback_url = status_callback_url
        self._client = None

        if not self.account_sid or not self.auth_token:
            logger.warning(
                "Twilio credentials not configured. "
                "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
            )

    def _get_client(self):
        """Lazy-init Twilio client."""
        if self._client is not None:
            return self._client

        from twilio.rest import Client

        self._client = Client(self.account_sid, self.auth_token)
        return self._client

    async def make_call(
        self,
        to_number: str,
        message: str,
        voice: str = "default",
        priority: str = "normal",
    ) -> dict:
        """Make an automated phone call with text-to-speech.

        Uses TwiML <Say> for text-to-speech. For critical priority,
        the message is repeated 3 times with pauses.
        """
        if not self.from_number:
            raise RuntimeError(
                "TWILIO_PHONE_NUMBER not configured. "
                "Set it to your Twilio phone number."
            )

        client = self._get_client()
        voice_name = self.VOICES.get(voice, self.VOICES["default"])

        # Build TwiML for the call
        twiml = f'<Response><Say voice="{voice_name}">{_escape_xml(message)}</Say>'
        if priority == "critical":
            # Repeat critical messages 3 times with pauses
            twiml += '<Pause length="2"/>'
            twiml += f'<Say voice="{voice_name}">I repeat: {_escape_xml(message)}</Say>'
            twiml += '<Pause length="2"/>'
            twiml += f'<Say voice="{voice_name}">Final repeat: {_escape_xml(message)}</Say>'
        twiml += "</Response>"

        kwargs: dict[str, Any] = {
            "to": to_number,
            "from_": self.from_number,
            "twiml": twiml,
        }

        if self.status_callback_url:
            kwargs["status_callback"] = self.status_callback_url
            kwargs["status_callback_event"] = ["initiated", "ringing", "answered", "completed"]

        # Twilio's client is synchronous — run in executor
        import asyncio
        loop = asyncio.get_event_loop()
        call = await loop.run_in_executor(None, lambda: client.calls.create(**kwargs))

        logger.info(f"Call initiated: {call.sid} to {to_number} (priority: {priority})")

        return {
            "call_id": call.sid,
            "status": call.status,
            "to": to_number,
            "from": self.from_number,
            "priority": priority,
        }

    async def get_call_status(self, call_id: str) -> dict:
        """Get the current status of a Twilio call."""
        client = self._get_client()

        import asyncio
        loop = asyncio.get_event_loop()
        call = await loop.run_in_executor(
            None, lambda: client.calls(call_id).fetch()
        )

        return {
            "call_id": call.sid,
            "status": call.status,
            "duration": int(call.duration or 0),
            "answered": call.status == "completed" and int(call.duration or 0) > 0,
            "direction": call.direction,
            "from": call.from_formatted,
            "to": call.to_formatted,
            "start_time": call.start_time.isoformat() if call.start_time else None,
            "end_time": call.end_time.isoformat() if call.end_time else None,
            "price": call.price,
            "price_unit": call.price_unit,
        }

    async def send_sms(
        self,
        to_number: str,
        message: str,
    ) -> dict:
        """Send an SMS via Twilio."""
        if not self.from_number:
            raise RuntimeError("TWILIO_PHONE_NUMBER not configured.")

        client = self._get_client()

        import asyncio
        loop = asyncio.get_event_loop()
        msg = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                to=to_number,
                from_=self.from_number,
                body=message[:1600],  # Twilio max ~1600 chars
            ),
        )

        logger.info(f"SMS sent: {msg.sid} to {to_number}")

        return {
            "message_id": msg.sid,
            "status": msg.status,
            "to": to_number,
            "from": self.from_number,
        }


def _escape_xml(text: str) -> str:
    """Escape text for safe inclusion in TwiML XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
