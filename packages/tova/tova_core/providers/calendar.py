"""
Abstract calendar provider interface.

Implement this class to connect Tova to calendar services.
Supports: Google Calendar, Microsoft Outlook, CalDAV, etc.
"""

from abc import ABC, abstractmethod


class BaseCalendarProvider(ABC):
    """Calendar provider for managing events and schedules."""

    @abstractmethod
    async def list_events(
        self,
        user_id: str,
        start: str,
        end: str,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """List events within a date range.

        Args:
            user_id: Tova user ID
            start: ISO datetime string (start of range)
            end: ISO datetime string (end of range)
            calendar_id: Calendar identifier (default: primary)

        Returns:
            List of dicts: [{id, title, start, end, location, attendees, description, status}]
        """
        ...

    @abstractmethod
    async def create_event(
        self,
        user_id: str,
        event_data: dict,
    ) -> dict:
        """Create a new calendar event.

        Args:
            event_data: {title, start, end, location?, description?, attendees?, reminders?}

        Returns:
            The created event dict with id
        """
        ...

    @abstractmethod
    async def update_event(
        self,
        user_id: str,
        event_id: str,
        updates: dict,
    ) -> dict:
        """Update an existing event. Returns the updated event."""
        ...

    @abstractmethod
    async def delete_event(
        self,
        user_id: str,
        event_id: str,
    ) -> bool:
        """Delete an event. Returns True if deleted."""
        ...

    async def find_free_slots(
        self,
        user_id: str,
        start: str,
        end: str,
        duration_minutes: int = 60,
    ) -> list[dict]:
        """Find available time slots in a date range.

        Returns:
            List of dicts: [{start, end}] representing free slots
        """
        raise NotImplementedError
