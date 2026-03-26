"""
Abstract telephony interface for phone calls and SMS.

Implement this class to connect Tova to your telephony provider.
Supports: Twilio, Vonage, Africa's Talking, etc.
"""

from abc import ABC, abstractmethod


class BaseTelephony(ABC):
    """Telephony provider for making calls and sending SMS.

    Used by the emergency system and notification tools.
    """

    @abstractmethod
    async def make_call(
        self,
        to_number: str,
        message: str,
        voice: str = "default",
        priority: str = "normal",
    ) -> dict:
        """Make an automated phone call with text-to-speech.

        Args:
            to_number: Phone number to call (E.164 format: +1234567890)
            message: Text to speak via TTS
            voice: Voice selection (provider-specific)
            priority: Call priority: "normal", "high", "critical"

        Returns:
            {"call_id": str, "status": str, "to": str}
        """
        ...

    @abstractmethod
    async def get_call_status(self, call_id: str) -> dict:
        """Get the current status of a call.

        Returns:
            {"call_id": str, "status": str, "duration": int, "answered": bool}
        """
        ...

    async def send_sms(
        self,
        to_number: str,
        message: str,
    ) -> dict:
        """Send an SMS message.

        Args:
            to_number: Phone number (E.164 format)
            message: SMS text (max ~160 chars for single SMS)

        Returns:
            {"message_id": str, "status": str, "to": str}
        """
        raise NotImplementedError
