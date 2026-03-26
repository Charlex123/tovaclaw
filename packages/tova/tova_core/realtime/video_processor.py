"""
Video frame analysis processor for CCTV monitoring.

Background worker that pulls frames from cameras, runs analysis
(object detection or LLM vision), and generates alerts.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime
from typing import Any

from tova_core.providers.store import BaseStore
from tova_core.providers.video_stream import BaseVideoStream
from tova_core.providers.notifier import BaseNotifier

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Background processor for CCTV frame analysis.

    Modes:
    - "fast": Uses YOLO or similar model for object detection (local)
    - "smart": Uses LLM vision (Claude/GPT-4V) for scene understanding

    Alert deduplication: Won't re-alert for the same detection within
    the cooldown period.
    """

    def __init__(
        self,
        video_stream: BaseVideoStream,
        store: BaseStore,
        notifier: BaseNotifier | None = None,
        analysis_interval: int = 5,
        alert_cooldown: int = 300,
        mode: str = "smart",
    ):
        self.video_stream = video_stream
        self.store = store
        self.notifier = notifier
        self.analysis_interval = analysis_interval
        self.alert_cooldown = alert_cooldown
        self.mode = mode
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_alerts: dict[str, datetime] = {}  # camera_id -> last alert time

    async def start(self) -> None:
        """Start the video processing loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info(
            f"Video processor started (interval: {self.analysis_interval}s, mode: {self.mode})"
        )

    async def stop(self) -> None:
        """Stop the processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Video processor stopped")

    async def _process_loop(self) -> None:
        """Main processing loop — analyze all active cameras."""
        while self._running:
            try:
                cameras = await self.video_stream.list_cameras()
                for camera in cameras:
                    if camera.get("status") == "active":
                        await self._analyze_camera(camera)
            except Exception as e:
                logger.error(f"Video processor error: {e}")
            await asyncio.sleep(self.analysis_interval)

    async def _analyze_camera(self, camera: dict[str, Any]) -> None:
        """Capture and analyze a frame from a camera."""
        camera_id = camera.get("camera_id", "")
        try:
            frame = await self.video_stream.get_frame(camera_id)
        except Exception as e:
            logger.warning(f"Failed to get frame from camera {camera_id}: {e}")
            return

        if not frame:
            return

        # Run analysis based on mode
        if self.mode == "fast":
            detections = await self._analyze_yolo(frame, camera_id)
        else:
            detections = await self._analyze_llm_vision(frame, camera_id)

        # Generate alerts for significant detections
        if detections and self._should_alert(camera_id):
            await self._create_alert(camera_id, camera, detections)

    async def _analyze_yolo(
        self, frame: bytes, camera_id: str
    ) -> list[dict]:
        """Run YOLO object detection on a frame."""
        try:
            from ultralytics import YOLO
            import numpy as np
            from PIL import Image
            import io

            model = YOLO("yolov8n.pt")
            image = Image.open(io.BytesIO(frame))
            results = model(image, verbose=False)

            detections = []
            for result in results:
                for box in result.boxes:
                    detections.append({
                        "class": result.names[int(box.cls[0])],
                        "confidence": float(box.conf[0]),
                        "bbox": box.xyxy[0].tolist(),
                    })
            return detections

        except ImportError:
            logger.warning("ultralytics not installed, falling back to smart mode")
            return await self._analyze_llm_vision(frame, camera_id)
        except Exception as e:
            logger.warning(f"YOLO analysis failed: {e}")
            return []

    async def _analyze_llm_vision(
        self, frame: bytes, camera_id: str
    ) -> list[dict]:
        """Analyze frame using LLM vision API.

        Sends the frame to Claude/GPT-4V for scene description and anomaly detection.
        """
        frame_b64 = base64.b64encode(frame).decode("utf-8")

        try:
            from tova_core.llm import build_llm
            llm = build_llm()

            response = await llm.ainvoke([
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (
                            "Analyze this CCTV camera frame. Report:\n"
                            "1. People count and activity\n"
                            "2. Vehicles detected\n"
                            "3. Any suspicious or unusual activity\n"
                            "4. Overall scene description\n"
                            "Respond in JSON format with keys: "
                            "people_count, vehicles, suspicious_activity (bool), "
                            "description, anomalies (list of strings)"
                        )},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_b64}"
                        }},
                    ],
                }
            ])

            import json
            try:
                analysis = json.loads(response.content)
                detections = []
                if analysis.get("people_count", 0) > 0:
                    detections.append({
                        "class": "person",
                        "count": analysis["people_count"],
                    })
                for anomaly in analysis.get("anomalies", []):
                    detections.append({
                        "class": "anomaly",
                        "description": anomaly,
                    })
                if analysis.get("suspicious_activity"):
                    detections.append({
                        "class": "suspicious_activity",
                        "description": analysis.get("description", ""),
                    })
                return detections
            except json.JSONDecodeError:
                return [{"class": "scene", "description": response.content}]

        except Exception as e:
            logger.warning(f"LLM vision analysis failed for camera {camera_id}: {e}")
            return []

    def _should_alert(self, camera_id: str) -> bool:
        """Check if we should create a new alert (cooldown dedup)."""
        now = datetime.now()
        last = self._last_alerts.get(camera_id)
        if last and (now - last).total_seconds() < self.alert_cooldown:
            return False
        self._last_alerts[camera_id] = now
        return True

    async def _create_alert(
        self,
        camera_id: str,
        camera: dict,
        detections: list[dict],
    ) -> None:
        """Create an alert from detections."""
        has_suspicious = any(
            d.get("class") in ("suspicious_activity", "anomaly")
            for d in detections
        )
        severity = "high" if has_suspicious else "low"

        alert = {
            "type": "cctv",
            "source": f"camera_{camera_id}",
            "severity": severity,
            "message": f"Detection on camera '{camera.get('name', camera_id)}': "
                       + ", ".join(d.get("class", "unknown") for d in detections[:5]),
            "data": {
                "camera_id": camera_id,
                "camera_name": camera.get("name", ""),
                "detections": detections,
                "timestamp": datetime.now().isoformat(),
            },
        }

        try:
            await self.store.save_alert(
                user_id=camera.get("user_id", ""),
                alert=alert,
            )
        except (NotImplementedError, Exception) as e:
            logger.warning(f"Failed to save CCTV alert: {e}")

        if self.notifier and has_suspicious:
            try:
                user_id = camera.get("user_id", "")
                if user_id:
                    await self.notifier.notify(
                        user_id=user_id,
                        title="CCTV Alert",
                        body=alert["message"],
                        data={"camera_id": camera_id},
                    )
            except Exception as e:
                logger.warning(f"Failed to send CCTV notification: {e}")
