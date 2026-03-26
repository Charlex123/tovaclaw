"""
CCTV / Video monitoring tools.

Enable agents to interact with camera feeds, analyze frames, and view alerts.
"""

from __future__ import annotations

import base64
import logging
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.providers.video_stream import BaseVideoStream

logger = logging.getLogger(__name__)


def build_cctv_tools(
    store: BaseStore,
    video_stream: BaseVideoStream,
) -> list:
    """Build CCTV monitoring tools using the provider pattern."""

    @tool
    async def list_cameras() -> dict:
        """List all registered CCTV cameras and their status."""
        try:
            cameras = await video_stream.list_cameras()
            return {
                "cameras": [
                    {
                        "camera_id": c.get("camera_id", ""),
                        "name": c.get("name", ""),
                        "status": c.get("status", "unknown"),
                        "location": c.get("location", ""),
                    }
                    for c in cameras
                ],
                "count": len(cameras),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def get_camera_snapshot(camera_id: str) -> dict:
        """Capture the current frame from a camera.

        Returns the frame as base64-encoded JPEG for display.

        Args:
            camera_id: The camera to capture from
        """
        try:
            frame = await video_stream.get_frame(camera_id)
            if not frame:
                return {"error": "No frame available"}

            frame_b64 = base64.b64encode(frame).decode("utf-8")
            return {
                "camera_id": camera_id,
                "frame_base64": frame_b64,
                "format": "jpeg",
                "size_bytes": len(frame),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def analyze_frame(camera_id: str) -> dict:
        """Capture and analyze the current frame from a camera using AI vision.

        Detects people, vehicles, and any suspicious activity.

        Args:
            camera_id: The camera to analyze
        """
        try:
            frame = await video_stream.get_frame(camera_id)
            if not frame:
                return {"error": "No frame available"}

            frame_b64 = base64.b64encode(frame).decode("utf-8")

            # Return frame for the agent's own vision analysis
            return {
                "camera_id": camera_id,
                "frame_base64": frame_b64,
                "format": "jpeg",
                "instruction": (
                    "Analyze this camera frame. Report:\n"
                    "1. Number of people visible\n"
                    "2. Vehicles detected\n"
                    "3. Any suspicious or unusual activity\n"
                    "4. General scene description"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def check_for_anomalies(camera_id: str) -> dict:
        """Check a camera feed for anomalies by analyzing the current frame.

        Args:
            camera_id: The camera to check
        """
        try:
            frame = await video_stream.get_frame(camera_id)
            if not frame:
                return {"error": "No frame available"}

            frame_b64 = base64.b64encode(frame).decode("utf-8")
            return {
                "camera_id": camera_id,
                "frame_base64": frame_b64,
                "instruction": (
                    "Analyze this CCTV frame for anomalies:\n"
                    "- Unauthorized access or trespassing\n"
                    "- Unattended objects/packages\n"
                    "- Crowd formation or unusual gatherings\n"
                    "- Vehicles in restricted areas\n"
                    "- Any other suspicious behavior\n"
                    "Report: anomaly_detected (bool), anomalies (list), risk_level (low/medium/high)"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_recent_alerts(
        user_id: str,
        alert_type: str = "cctv",
        limit: int = 20,
    ) -> dict:
        """List recent alerts from CCTV cameras or other monitoring systems.

        Args:
            user_id: The user whose alerts to list
            alert_type: Filter by type: cctv, vehicle, emergency, all
            limit: Maximum alerts to return
        """
        try:
            alerts = await store.list_alerts(
                user_id=user_id,
                alert_type=alert_type if alert_type != "all" else None,
                limit=limit,
            )
            return {
                "alerts": [
                    {
                        "id": a.get("id", ""),
                        "type": a.get("type", ""),
                        "severity": a.get("severity", ""),
                        "message": a.get("message", ""),
                        "source": a.get("source", ""),
                        "acknowledged": a.get("acknowledged", False),
                        "created_at": a.get("created_at", ""),
                    }
                    for a in alerts
                ],
                "count": len(alerts),
            }
        except (NotImplementedError, Exception) as e:
            return {"alerts": [], "count": 0}

    return [list_cameras, get_camera_snapshot, analyze_frame, check_for_anomalies, list_recent_alerts]
