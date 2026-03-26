"""
Emergency tracking and alert tools.

Enable agents to report, track, and escalate emergencies.
"""

from __future__ import annotations

import logging
from datetime import datetime
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.providers.notifier import BaseNotifier
from tova_core.providers.telephony import BaseTelephony

logger = logging.getLogger(__name__)


def build_emergency_tools(
    store: BaseStore,
    notifier: BaseNotifier | None = None,
    telephony: BaseTelephony | None = None,
) -> list:
    """Build emergency tracking tools using the provider pattern."""

    @tool
    async def report_emergency(
        user_id: str,
        emergency_type: str,
        severity: str = "high",
        description: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
        contact_numbers: str = "",
    ) -> dict:
        """Report a new emergency.

        Args:
            user_id: The user reporting the emergency
            emergency_type: Type: fire, medical, security, accident, natural_disaster, other
            severity: Severity level: critical, high, medium, low
            description: Description of the emergency
            latitude: Location latitude (0 if unknown)
            longitude: Location longitude (0 if unknown)
            contact_numbers: Comma-separated phone numbers to notify
        """
        try:
            emergency = {
                "reporter_id": user_id,
                "type": emergency_type,
                "severity": severity,
                "description": description,
                "status": "reported",
                "latitude": latitude if latitude else None,
                "longitude": longitude if longitude else None,
                "contact_numbers": [n.strip() for n in contact_numbers.split(",") if n.strip()] if contact_numbers else [],
                "assigned_to": [],
                "escalation_level": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            emergency_id = await store.save_emergency(emergency)

            # Immediate notification for critical emergencies
            if severity == "critical" and notifier:
                await notifier.notify(
                    user_id=user_id,
                    title=f"CRITICAL EMERGENCY: {emergency_type}",
                    body=description[:200],
                    data={"emergency_id": emergency_id},
                )

            return {
                "success": True,
                "id": emergency_id,
                "type": emergency_type,
                "severity": severity,
                "status": "reported",
            }
        except NotImplementedError:
            return {"error": "Emergency storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_emergencies(
        status: str = "",
        severity: str = "",
    ) -> dict:
        """List active emergencies, optionally filtered.

        Args:
            status: Filter by status: reported, acknowledged, in_progress, resolved, escalated
            severity: Filter by severity: critical, high, medium, low
        """
        try:
            filters = {}
            if status:
                filters["status"] = status
            if severity:
                filters["severity"] = severity

            emergencies = await store.list_emergencies(filters=filters or None)
            return {
                "emergencies": [
                    {
                        "id": e.get("id", ""),
                        "type": e.get("type", ""),
                        "severity": e.get("severity", ""),
                        "status": e.get("status", ""),
                        "description": e.get("description", "")[:200],
                        "escalation_level": e.get("escalation_level", 0),
                        "created_at": e.get("created_at", ""),
                    }
                    for e in emergencies
                ],
                "count": len(emergencies),
            }
        except NotImplementedError:
            return {"emergencies": [], "count": 0}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def escalate_emergency(emergency_id: str) -> dict:
        """Manually escalate an emergency to the next level.

        This triggers additional notifications (SMS, phone calls) based on the new level.

        Args:
            emergency_id: The emergency ID to escalate
        """
        try:
            emergencies = await store.list_emergencies(filters=None)
            emergency = next((e for e in emergencies if e.get("id") == emergency_id), None)
            if not emergency:
                return {"error": f"Emergency {emergency_id} not found"}

            new_level = emergency.get("escalation_level", 0) + 1
            await store.update_emergency(emergency_id, {
                "escalation_level": new_level,
                "status": "escalated",
                "updated_at": datetime.now().isoformat(),
            })

            return {
                "success": True,
                "id": emergency_id,
                "new_level": new_level,
                "status": "escalated",
            }
        except NotImplementedError:
            return {"error": "Emergency storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def trigger_emergency_call(
        emergency_id: str,
        phone_number: str,
    ) -> dict:
        """Make an emergency phone call to notify someone.

        Args:
            emergency_id: The emergency this call is about
            phone_number: Phone number to call (E.164 format: +1234567890)
        """
        if not telephony:
            return {"error": "Telephony not configured"}

        try:
            emergencies = await store.list_emergencies(filters=None)
            emergency = next((e for e in emergencies if e.get("id") == emergency_id), None)
            if not emergency:
                return {"error": f"Emergency {emergency_id} not found"}

            result = await telephony.make_call(
                to_number=phone_number,
                message=(
                    f"This is an automated emergency alert from Tova. "
                    f"Emergency type: {emergency.get('type', 'unknown')}. "
                    f"Severity: {emergency.get('severity', 'unknown')}. "
                    f"{emergency.get('description', '')}. "
                    f"Please respond immediately."
                ),
                priority="critical",
            )
            return {
                "success": True,
                "call_id": result.get("call_id", ""),
                "status": result.get("status", ""),
                "to": phone_number,
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def send_emergency_alert(
        emergency_id: str,
        user_ids: str = "",
    ) -> dict:
        """Send push notification alert about an emergency to specified users.

        Args:
            emergency_id: The emergency to alert about
            user_ids: Comma-separated user IDs to notify (empty = notify reporter)
        """
        if not notifier:
            return {"error": "Notifications not configured"}

        try:
            emergencies = await store.list_emergencies(filters=None)
            emergency = next((e for e in emergencies if e.get("id") == emergency_id), None)
            if not emergency:
                return {"error": f"Emergency {emergency_id} not found"}

            targets = [u.strip() for u in user_ids.split(",") if u.strip()] if user_ids else [emergency.get("reporter_id", "")]
            sent = 0
            for uid in targets:
                try:
                    await notifier.notify(
                        user_id=uid,
                        title=f"Emergency Alert: {emergency.get('type', '')} ({emergency.get('severity', '')})",
                        body=emergency.get("description", "")[:200],
                        data={"emergency_id": emergency_id},
                    )
                    sent += 1
                except Exception:
                    pass

            return {"success": True, "alerts_sent": sent, "total_targets": len(targets)}
        except Exception as e:
            return {"error": str(e)}

    return [report_emergency, list_emergencies, escalate_emergency, trigger_emergency_call, send_emergency_alert]
