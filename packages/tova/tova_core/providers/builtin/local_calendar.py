"""
Local calendar provider — no Google, no OAuth, always works.

Stores events in the Tova SQLite database. Every user gets a calendar
automatically — no setup, no external accounts.

This is the DEFAULT calendar for regular users. Events are stored
locally and can be synced to Google Calendar later if the user
connects their account.

Usage:
    calendar = LocalCalendarProvider(store=my_store)
    await calendar.create_event("user_123", {
        "title": "Dentist appointment",
        "start": "2026-03-26T14:00:00",
        "end": "2026-03-26T15:00:00",
    })
    events = await calendar.list_events("user_123", "2026-03-25", "2026-03-31")
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from tova_core.providers.calendar import BaseCalendarProvider
from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


class LocalCalendarProvider(BaseCalendarProvider):
    """SQLite-backed local calendar — zero config, always available.

    Events stored in the Tova store. No external API needed.
    Works for every user out of the box.
    """

    def __init__(self, store: BaseStore):
        self.store = store

    async def list_events(
        self,
        user_id: str,
        start: str,
        end: str,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """List events within a date range from local store."""
        try:
            all_events = await self.store.list_events(
                user_id, start=start, end=end
            )
        except NotImplementedError:
            return []

        # Normalize and sort by start time
        events = []
        for event in all_events:
            events.append({
                "id": event.get("id", ""),
                "title": event.get("title", "(no title)"),
                "description": event.get("description", ""),
                "start": event.get("start_time", event.get("start", "")),
                "end": event.get("end_time", event.get("end", "")),
                "location": event.get("location", ""),
                "attendees": event.get("attendees", []),
                "status": event.get("status", "scheduled"),
                "reminders": event.get("reminders", []),
                "recurrence": event.get("recurrence", ""),
                "recurring": bool(event.get("recurrence")),
                "html_link": "",
            })

        events.sort(key=lambda e: e.get("start", ""))
        return events

    async def create_event(
        self,
        user_id: str,
        event_data: dict,
    ) -> dict:
        """Create a new event in local store."""
        now = datetime.now(timezone.utc).isoformat()
        event = {
            "title": event_data.get("title", ""),
            "description": event_data.get("description", ""),
            "start_time": event_data.get("start", event_data.get("start_time", "")),
            "end_time": event_data.get("end", event_data.get("end_time", "")),
            "location": event_data.get("location", ""),
            "attendees": event_data.get("attendees", []),
            "reminders": event_data.get("reminders", []),
            "recurrence": event_data.get("recurrence", ""),
            "status": "scheduled",
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }

        try:
            event_id = await self.store.save_event(user_id, event)
            event["id"] = event_id
        except NotImplementedError:
            event["id"] = str(uuid.uuid4())

        logger.info(f"Event created: '{event['title']}' for user {user_id[:16]}...")

        return {
            "id": event["id"],
            "title": event["title"],
            "start": event["start_time"],
            "end": event["end_time"],
            "location": event.get("location", ""),
            "status": "created",
            "html_link": "",
        }

    async def update_event(
        self,
        user_id: str,
        event_id: str,
        updates: dict,
    ) -> dict:
        """Update an event in local store."""
        # Map field names
        store_updates = {}
        if "title" in updates:
            store_updates["title"] = updates["title"]
        if "description" in updates:
            store_updates["description"] = updates["description"]
        if "start" in updates:
            store_updates["start_time"] = updates["start"]
        if "end" in updates:
            store_updates["end_time"] = updates["end"]
        if "location" in updates:
            store_updates["location"] = updates["location"]
        if "status" in updates:
            store_updates["status"] = updates["status"]
        if "attendees" in updates:
            store_updates["attendees"] = updates["attendees"]
        if "reminders" in updates:
            store_updates["reminders"] = updates["reminders"]

        store_updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            await self.store.update_event(event_id, store_updates)
        except NotImplementedError:
            pass

        return {
            "id": event_id,
            "status": "updated",
            **{k: v for k, v in updates.items() if k in ("title", "start", "end")},
        }

    async def delete_event(
        self,
        user_id: str,
        event_id: str,
    ) -> bool:
        """Delete an event from local store."""
        try:
            return await self.store.delete_event(event_id)
        except NotImplementedError:
            return False

    async def find_free_slots(
        self,
        user_id: str,
        start: str,
        end: str,
        duration_minutes: int = 60,
    ) -> list[dict]:
        """Find available time slots by analyzing existing events."""
        events = await self.list_events(user_id, start, end)

        # Parse busy periods
        busy = []
        for event in events:
            try:
                evt_start = datetime.fromisoformat(
                    event["start"].replace("Z", "+00:00")
                )
                evt_end = datetime.fromisoformat(
                    event["end"].replace("Z", "+00:00")
                )
                busy.append((evt_start, evt_end))
            except (ValueError, KeyError):
                continue

        busy.sort(key=lambda x: x[0])

        # Find gaps
        try:
            range_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            range_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            return []

        duration = timedelta(minutes=duration_minutes)
        free_slots = []
        current = range_start

        for busy_start, busy_end in busy:
            if busy_start - current >= duration:
                slot = current
                while slot + duration <= busy_start:
                    if 8 <= slot.hour < 18:  # Business hours
                        free_slots.append({
                            "start": slot.isoformat(),
                            "end": (slot + duration).isoformat(),
                        })
                    slot += timedelta(minutes=30)
            current = max(current, busy_end)

        # After last event
        if range_end - current >= duration:
            slot = current
            while slot + duration <= range_end and len(free_slots) < 10:
                if 8 <= slot.hour < 18:
                    free_slots.append({
                        "start": slot.isoformat(),
                        "end": (slot + duration).isoformat(),
                    })
                slot += timedelta(minutes=30)

        return free_slots[:10]
