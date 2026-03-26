"""
RTSP/HTTP video stream provider — connects to IP cameras.

Captures frames from RTSP, HTTP, and ONVIF cameras using OpenCV.
Supports multiple concurrent cameras with per-camera state tracking.

Usage:
    stream = RTSPVideoStream(store=my_store)

    # Register a camera
    await stream.connect_camera(
        camera_id="front_door",
        url="rtsp://admin:pass@192.168.1.100:554/stream",
    )

    # Capture a frame
    frame_bytes = await stream.get_frame("front_door")

    # List all cameras
    cameras = await stream.list_cameras()

Install: pip install tova[video]  (opencv-python, ultralytics)

Supported protocols:
    - RTSP (rtsp://...) — most IP cameras
    - HTTP/HTTPS (http://...) — MJPEG streams, snapshot URLs
    - Local device (int) — USB/built-in webcams (0, 1, 2...)
"""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import datetime, timezone
from typing import Any

from tova_core.providers.video_stream import BaseVideoStream
from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


class RTSPVideoStream(BaseVideoStream):
    """OpenCV-based video stream provider for RTSP/HTTP cameras.

    Each camera maintains its own capture session. Frames are captured
    on-demand (not continuously buffered) to minimize resource usage.
    """

    def __init__(
        self,
        store: BaseStore | None = None,
        connection_timeout: int = 10,
        frame_quality: int = 85,
    ):
        self.store = store
        self.connection_timeout = connection_timeout
        self.frame_quality = frame_quality
        # camera_id -> {url, protocol, capture, status, ...}
        self._cameras: dict[str, dict[str, Any]] = {}

    async def connect_camera(
        self,
        camera_id: str,
        url: str,
        protocol: str = "rtsp",
        credentials: dict | None = None,
    ) -> dict:
        """Connect to a camera feed via OpenCV."""
        import cv2

        # Build full URL with credentials if needed
        full_url = url
        if credentials and protocol in ("rtsp", "http", "https"):
            username = credentials.get("username", "")
            password = credentials.get("password", "")
            if username:
                # Insert credentials into URL: rtsp://user:pass@host/path
                proto_end = url.index("://") + 3
                full_url = f"{url[:proto_end]}{username}:{password}@{url[proto_end:]}"

        # Open capture in executor (blocking I/O)
        loop = asyncio.get_event_loop()

        def _open_capture():
            cap = cv2.VideoCapture(full_url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.connection_timeout * 1000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
            if not cap.isOpened():
                raise ConnectionError(f"Failed to connect to camera at {url}")
            # Read one test frame
            ret, frame = cap.read()
            if not ret:
                cap.release()
                raise ConnectionError(f"Connected but failed to read frame from {url}")
            h, w = frame.shape[:2]
            return cap, w, h

        try:
            cap, width, height = await loop.run_in_executor(None, _open_capture)
        except Exception as e:
            logger.error(f"Camera {camera_id} connection failed: {e}")
            self._cameras[camera_id] = {
                "camera_id": camera_id,
                "url": url,
                "protocol": protocol,
                "status": "error",
                "error": str(e),
                "capture": None,
            }
            raise

        camera_info = {
            "camera_id": camera_id,
            "url": url,
            "protocol": protocol,
            "status": "active",
            "capture": cap,
            "resolution": f"{width}x{height}",
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_frame_at": None,
            "frame_count": 0,
        }
        self._cameras[camera_id] = camera_info

        # Persist camera metadata (without cv2 capture object)
        if self.store:
            try:
                meta = {k: v for k, v in camera_info.items() if k != "capture"}
                await self.store.save_alert(
                    user_id="__system__",
                    alert={"type": "camera_registered", "data": meta},
                )
            except (NotImplementedError, Exception):
                pass

        logger.info(f"Camera '{camera_id}' connected: {width}x{height} via {protocol}")
        return {
            "camera_id": camera_id,
            "status": "active",
            "resolution": f"{width}x{height}",
        }

    async def get_frame(self, camera_id: str) -> bytes:
        """Capture the latest frame from a camera as JPEG bytes."""
        camera = self._cameras.get(camera_id)
        if not camera or not camera.get("capture"):
            raise RuntimeError(f"Camera '{camera_id}' not connected")

        import cv2

        cap = camera["capture"]
        loop = asyncio.get_event_loop()

        def _read_frame():
            # Grab latest frame (skip buffered frames for RTSP)
            cap.grab()
            ret, frame = cap.retrieve()
            if not ret:
                raise RuntimeError(f"Failed to read frame from camera '{camera_id}'")
            # Encode as JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.frame_quality]
            success, buffer = cv2.imencode(".jpg", frame, encode_params)
            if not success:
                raise RuntimeError("Failed to encode frame as JPEG")
            return buffer.tobytes()

        try:
            frame_bytes = await loop.run_in_executor(None, _read_frame)
        except Exception as e:
            # Try reconnecting
            logger.warning(f"Frame read failed for '{camera_id}', attempting reconnect: {e}")
            camera["status"] = "reconnecting"
            try:
                cap.release()
                url = camera["url"]
                credentials = camera.get("credentials")
                protocol = camera.get("protocol", "rtsp")
                await self.connect_camera(camera_id, url, protocol, credentials)
                # Retry frame read
                frame_bytes = await loop.run_in_executor(None, _read_frame)
            except Exception as re_err:
                camera["status"] = "error"
                raise RuntimeError(f"Camera '{camera_id}' reconnect failed: {re_err}")

        camera["last_frame_at"] = datetime.now(timezone.utc).isoformat()
        camera["frame_count"] = camera.get("frame_count", 0) + 1
        return frame_bytes

    async def list_cameras(self) -> list[dict]:
        """List all registered cameras with their status."""
        cameras = []
        for cam_id, cam in self._cameras.items():
            cameras.append({
                "camera_id": cam_id,
                "name": cam.get("name", cam_id),
                "url": cam.get("url", ""),
                "protocol": cam.get("protocol", ""),
                "status": cam.get("status", "unknown"),
                "resolution": cam.get("resolution", ""),
                "last_frame_at": cam.get("last_frame_at"),
                "frame_count": cam.get("frame_count", 0),
                "connected_at": cam.get("connected_at"),
            })
        return cameras

    async def disconnect_camera(self, camera_id: str) -> bool:
        """Disconnect and release a camera."""
        camera = self._cameras.pop(camera_id, None)
        if not camera:
            return False

        cap = camera.get("capture")
        if cap:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, cap.release)

        logger.info(f"Camera '{camera_id}' disconnected")
        return True

    async def start_recording(
        self,
        camera_id: str,
        duration_seconds: int = 0,
    ) -> dict:
        """Start recording from a camera to file.

        Records to an MP4 file using H.264 codec.
        """
        camera = self._cameras.get(camera_id)
        if not camera or not camera.get("capture"):
            raise RuntimeError(f"Camera '{camera_id}' not connected")

        import cv2
        import tempfile
        import os

        cap = camera["capture"]
        fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Create output file
        recording_id = f"rec_{camera_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        output_dir = os.path.expanduser("~/.tova/recordings")
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{recording_id}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

        camera["recording"] = {
            "recording_id": recording_id,
            "writer": writer,
            "file_path": file_path,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "duration_limit": duration_seconds,
            "frame_count": 0,
        }

        # Start recording in background
        async def _record():
            start = asyncio.get_event_loop().time()
            while camera_id in self._cameras and "recording" in camera:
                rec = camera.get("recording")
                if not rec:
                    break
                if duration_seconds and (asyncio.get_event_loop().time() - start) >= duration_seconds:
                    break
                try:
                    frame_bytes = await self.get_frame(camera_id)
                    import numpy as np
                    nparr = np.frombuffer(frame_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        writer.write(frame)
                        rec["frame_count"] += 1
                except Exception:
                    break
                await asyncio.sleep(1.0 / fps)
            writer.release()

        camera["recording_task"] = asyncio.create_task(_record())

        logger.info(f"Recording started: {recording_id}")
        return {"recording_id": recording_id, "status": "recording", "file_path": file_path}

    async def stop_recording(self, recording_id: str) -> dict:
        """Stop an active recording."""
        for cam_id, camera in self._cameras.items():
            rec = camera.get("recording")
            if rec and rec.get("recording_id") == recording_id:
                task = camera.pop("recording_task", None)
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                recording = camera.pop("recording", {})
                writer = recording.get("writer")
                if writer:
                    writer.release()
                return {
                    "recording_id": recording_id,
                    "status": "stopped",
                    "file_path": recording.get("file_path", ""),
                    "frame_count": recording.get("frame_count", 0),
                }

        return {"recording_id": recording_id, "status": "not_found"}

    async def get_recording(self, recording_id: str) -> dict:
        """Get recording metadata."""
        for cam_id, camera in self._cameras.items():
            rec = camera.get("recording")
            if rec and rec.get("recording_id") == recording_id:
                return {
                    "recording_id": recording_id,
                    "camera_id": cam_id,
                    "file_path": rec.get("file_path", ""),
                    "frame_count": rec.get("frame_count", 0),
                    "status": "recording",
                    "start_time": rec.get("start_time"),
                }
        return {"recording_id": recording_id, "status": "not_found"}
