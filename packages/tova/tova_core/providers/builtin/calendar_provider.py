"""
Google Calendar provider — OAuth2 + Google Calendar API.

Manages calendar events, finds free slots, and syncs with users'
Google Calendar accounts. Each user authorizes their own account.

Usage:
    # From env vars:
    GOOGLE_CALENDAR_CLIENT_ID=...
    GOOGLE_CALENDAR_CLIENT_SECRET=...
    provider = GoogleCalendarProvider(store=my_store)

    # Generate OAuth URL
    url = provider.get_auth_url(user_id)

    # After callback
    await provider.handle_oauth_callback(user_id, code)

    # List events
    events = await provider.list_events(user_id, "2026-03-25T00:00:00Z", "2026-03-31T23:59:59Z")

Install: pip install google-auth google-auth-httplib2 google-api-python-client
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from tova_core.providers.calendar import BaseCalendarProvider
from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


class GoogleCalendarProvider(BaseCalendarProvider):
    """Google Calendar provider with per-user OAuth2.

    Each user authorizes their own Google account. Tova can then
    read, create, update, and delete calendar events on their behalf.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        store: BaseStore | None = None,
    ):
        self.client_id = client_id or os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.environ.get(
            "GOOGLE_CALENDAR_REDIRECT_URI",
            "http://localhost:8000/auth/calendar/callback",
        )
        self.store = store
        self._creds_cache: dict[str, Any] = {}

    def get_auth_url(self, user_id: str) -> str:
        """Generate OAuth2 authorization URL for Google Calendar."""
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=CALENDAR_SCOPES,
        )
        flow.redirect_uri = self.redirect_uri

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=user_id,
        )
        return auth_url

    async def handle_oauth_callback(self, user_id: str, code: str) -> bool:
        """Exchange authorization code for tokens."""
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=CALENDAR_SCOPES,
        )
        flow.redirect_uri = self.redirect_uri

        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: flow.fetch_token(code=code))

        creds = flow.credentials
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or []),
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        }

        if self.store:
            try:
                await self.store.save_user_preferences(
                    user_id, "gcal_oauth", token_data
                )
            except NotImplementedError:
                pass

        self._creds_cache[user_id] = creds
        logger.info(f"Google Calendar connected for user {user_id[:16]}...")
        return True

    async def _get_credentials(self, user_id: str):
        """Load and refresh OAuth credentials."""
        if user_id in self._creds_cache:
            creds = self._creds_cache[user_id]
            if creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                import asyncio
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: creds.refresh(Request())
                )
            return creds

        if self.store:
            try:
                prefs = await self.store.get_user_preferences(user_id)
                token_data = prefs.get("gcal_oauth")
                if token_data:
                    from google.oauth2.credentials import Credentials
                    creds = Credentials(
                        token=token_data["token"],
                        refresh_token=token_data.get("refresh_token"),
                        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                        client_id=token_data.get("client_id", self.client_id),
                        client_secret=token_data.get("client_secret", self.client_secret),
                        scopes=token_data.get("scopes", CALENDAR_SCOPES),
                    )
                    if creds.expired and creds.refresh_token:
                        from google.auth.transport.requests import Request
                        import asyncio
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: creds.refresh(Request())
                        )
                    self._creds_cache[user_id] = creds
                    return creds
            except (NotImplementedError, Exception) as e:
                logger.debug(f"Could not load calendar tokens: {e}")

        return None

    def _build_service(self, creds):
        """Build Google Calendar API service."""
        from googleapiclient.discovery import build
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    async def list_events(
        self,
        user_id: str,
        start: str,
        end: str,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """List calendar events within a date range."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError("Google Calendar not connected. Use /auth/calendar to authorize.")

        import asyncio
        service = self._build_service(creds)

        # Ensure ISO format with timezone
        if not start.endswith("Z") and "+" not in start:
            start += "Z"
        if not end.endswith("Z") and "+" not in end:
            end += "Z"

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: service.events().list(
                calendarId=calendar_id,
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime",
                maxResults=250,
            ).execute(),
        )

        events = []
        for item in result.get("items", []):
            start_dt = item.get("start", {})
            end_dt = item.get("end", {})
            events.append({
                "id": item["id"],
                "title": item.get("summary", "(no title)"),
                "description": item.get("description", ""),
                "start": start_dt.get("dateTime", start_dt.get("date", "")),
                "end": end_dt.get("dateTime", end_dt.get("date", "")),
                "location": item.get("location", ""),
                "attendees": [
                    {
                        "email": a.get("email", ""),
                        "name": a.get("displayName", ""),
                        "status": a.get("responseStatus", ""),
                    }
                    for a in item.get("attendees", [])
                ],
                "status": item.get("status", "confirmed"),
                "html_link": item.get("htmlLink", ""),
                "recurring": bool(item.get("recurringEventId")),
            })

        return events

    async def create_event(
        self,
        user_id: str,
        event_data: dict,
    ) -> dict:
        """Create a new Google Calendar event."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError("Google Calendar not connected.")

        import asyncio
        service = self._build_service(creds)

        body: dict[str, Any] = {
            "summary": event_data.get("title", ""),
            "description": event_data.get("description", ""),
            "location": event_data.get("location", ""),
            "start": {"dateTime": event_data["start"], "timeZone": event_data.get("timezone", "UTC")},
            "end": {"dateTime": event_data["end"], "timeZone": event_data.get("timezone", "UTC")},
        }

        # Add attendees
        attendees = event_data.get("attendees", [])
        if attendees:
            body["attendees"] = [
                {"email": a} if isinstance(a, str) else a
                for a in attendees
            ]

        # Add reminders
        reminders = event_data.get("reminders", [])
        if reminders:
            body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": r.get("method", "popup"), "minutes": r.get("minutes", 30)}
                    for r in reminders
                ],
            }

        # Add recurrence
        recurrence = event_data.get("recurrence")
        if recurrence:
            body["recurrence"] = [recurrence] if isinstance(recurrence, str) else recurrence

        calendar_id = event_data.get("calendar_id", "primary")
        created = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: service.events().insert(
                calendarId=calendar_id,
                body=body,
                sendUpdates="all" if attendees else "none",
            ).execute(),
        )

        logger.info(f"Calendar event created: {created['id']}")
        return {
            "id": created["id"],
            "title": created.get("summary", ""),
            "start": created["start"].get("dateTime", ""),
            "end": created["end"].get("dateTime", ""),
            "html_link": created.get("htmlLink", ""),
            "status": "created",
        }

    async def update_event(
        self,
        user_id: str,
        event_id: str,
        updates: dict,
    ) -> dict:
        """Update an existing Google Calendar event."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError("Google Calendar not connected.")

        import asyncio
        service = self._build_service(creds)

        calendar_id = updates.pop("calendar_id", "primary")

        # Fetch existing event
        existing = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: service.events().get(
                calendarId=calendar_id, eventId=event_id
            ).execute(),
        )

        # Apply updates
        if "title" in updates:
            existing["summary"] = updates["title"]
        if "description" in updates:
            existing["description"] = updates["description"]
        if "location" in updates:
            existing["location"] = updates["location"]
        if "start" in updates:
            existing["start"] = {"dateTime": updates["start"]}
        if "end" in updates:
            existing["end"] = {"dateTime": updates["end"]}

        updated = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: service.events().update(
                calendarId=calendar_id, eventId=event_id, body=existing
            ).execute(),
        )

        return {
            "id": updated["id"],
            "title": updated.get("summary", ""),
            "start": updated["start"].get("dateTime", ""),
            "end": updated["end"].get("dateTime", ""),
            "status": "updated",
        }

    async def delete_event(
        self,
        user_id: str,
        event_id: str,
    ) -> bool:
        """Delete a Google Calendar event."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise PermissionError("Google Calendar not connected.")

        import asyncio
        service = self._build_service(creds)

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.events().delete(
                    calendarId="primary", eventId=event_id
                ).execute(),
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to delete calendar event {event_id}: {e}")
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

        # Parse all busy periods
        busy = []
        for event in events:
            try:
                event_start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
                event_end = datetime.fromisoformat(event["end"].replace("Z", "+00:00"))
                busy.append((event_start, event_end))
            except (ValueError, KeyError):
                continue

        busy.sort(key=lambda x: x[0])

        # Find gaps
        range_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        range_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        duration = timedelta(minutes=duration_minutes)

        free_slots = []
        current = range_start

        for busy_start, busy_end in busy:
            if busy_start - current >= duration:
                # Only suggest slots during business hours (8am-6pm)
                slot_start = current
                while slot_start + duration <= busy_start:
                    if 8 <= slot_start.hour < 18:
                        free_slots.append({
                            "start": slot_start.isoformat(),
                            "end": (slot_start + duration).isoformat(),
                        })
                    slot_start += timedelta(minutes=30)
            current = max(current, busy_end)

        # Check remaining time after last event
        if range_end - current >= duration:
            slot_start = current
            while slot_start + duration <= range_end and len(free_slots) < 10:
                if 8 <= slot_start.hour < 18:
                    free_slots.append({
                        "start": slot_start.isoformat(),
                        "end": (slot_start + duration).isoformat(),
                    })
                slot_start += timedelta(minutes=30)

        return free_slots[:10]  # Return max 10 slots
