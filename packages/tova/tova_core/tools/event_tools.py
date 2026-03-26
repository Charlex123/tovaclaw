"""
Event planning tools.

Enable agents to create, manage, and suggest events/calendar entries.
"""

from __future__ import annotations

import logging
from datetime import datetime
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.providers.notifier import BaseNotifier

logger = logging.getLogger(__name__)


def build_event_tools(
    store: BaseStore,
    notifier: BaseNotifier | None = None,
) -> list:
    """Build event planning tools using the provider pattern."""

    @tool
    async def create_event(
        user_id: str,
        title: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        attendees: str = "",
    ) -> dict:
        """Create a new event / calendar entry.

        Args:
            user_id: The user creating the event
            title: Event title
            start_time: Start time (ISO format: YYYY-MM-DDTHH:MM:SS)
            end_time: End time (ISO format: YYYY-MM-DDTHH:MM:SS)
            description: Event description
            location: Event location
            attendees: Comma-separated list of attendee names/emails
        """
        try:
            event_data = {
                "title": title,
                "description": description,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "attendees": [a.strip() for a in attendees.split(",") if a.strip()] if attendees else [],
                "reminders": [{"minutes_before": 30, "method": "push"}],
                "status": "scheduled",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            event_id = await store.save_event(user_id, event_data)
            return {"success": True, "id": event_id, "title": title, "start": start_time}
        except NotImplementedError:
            return {"error": "Event storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_events(
        user_id: str,
        start: str = "",
        end: str = "",
    ) -> dict:
        """List the user's upcoming events, optionally filtered by date range.

        Args:
            user_id: The user whose events to list
            start: Start of date range (ISO format, empty = today)
            end: End of date range (ISO format, empty = 30 days from now)
        """
        try:
            events = await store.list_events(
                user_id, start=start or None, end=end or None
            )
            return {
                "events": [
                    {
                        "id": e.get("id", ""),
                        "title": e.get("title", ""),
                        "start_time": e.get("start_time", ""),
                        "end_time": e.get("end_time", ""),
                        "location": e.get("location", ""),
                        "status": e.get("status", "scheduled"),
                        "attendees": e.get("attendees", []),
                    }
                    for e in events
                ],
                "count": len(events),
            }
        except NotImplementedError:
            return {"events": [], "count": 0}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def update_event(
        event_id: str,
        title: str = "",
        start_time: str = "",
        end_time: str = "",
        location: str = "",
        status: str = "",
    ) -> dict:
        """Update an existing event.

        Args:
            event_id: The event ID to update
            title: New title (empty = keep current)
            start_time: New start time (empty = keep current)
            end_time: New end time (empty = keep current)
            location: New location (empty = keep current)
            status: New status: scheduled, cancelled, completed (empty = keep current)
        """
        try:
            updates = {"updated_at": datetime.now().isoformat()}
            if title:
                updates["title"] = title
            if start_time:
                updates["start_time"] = start_time
            if end_time:
                updates["end_time"] = end_time
            if location:
                updates["location"] = location
            if status:
                updates["status"] = status

            success = await store.update_event(event_id, updates)
            return {"success": success, "id": event_id, "updates": updates}
        except NotImplementedError:
            return {"error": "Event storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def suggest_event_time(
        user_id: str,
        duration_minutes: int = 60,
        preferred_time: str = "afternoon",
    ) -> dict:
        """Suggest optimal times for a new event based on the user's existing schedule.

        Args:
            user_id: The user to check schedule for
            duration_minutes: How long the event should be
            preferred_time: Preference: morning, afternoon, evening, any
        """
        try:
            events = await store.list_events(user_id)
            busy_times = [
                {"start": e.get("start_time", ""), "end": e.get("end_time", "")}
                for e in events
                if e.get("status") == "scheduled"
            ]

            return {
                "existing_events_count": len(busy_times),
                "busy_times": busy_times[:10],
                "preferred_time": preferred_time,
                "duration_minutes": duration_minutes,
                "instruction": (
                    "Based on the user's busy times, suggest 3 available time slots "
                    f"for a {duration_minutes}-minute event, preferably in the {preferred_time}."
                ),
            }
        except NotImplementedError:
            return {"message": "Event storage not configured, suggest times freely"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def send_event_reminder(
        user_id: str,
        event_id: str,
    ) -> dict:
        """Send a reminder notification about an upcoming event.

        Args:
            user_id: The user to remind
            event_id: The event to remind about
        """
        if not notifier:
            return {"error": "Notifications not configured"}

        try:
            events = await store.list_events(user_id)
            event = next((e for e in events if e.get("id") == event_id), None)
            if not event:
                return {"error": f"Event {event_id} not found"}

            await notifier.notify(
                user_id=user_id,
                title=f"Event Reminder: {event.get('title', '')}",
                body=f"Starts at {event.get('start_time', '')} at {event.get('location', 'TBD')}",
                data={"event_id": event_id},
            )
            return {"success": True, "event": event.get("title", "")}
        except Exception as e:
            return {"error": str(e)}

    return [create_event, list_events, update_event, suggest_event_time, send_event_reminder]
