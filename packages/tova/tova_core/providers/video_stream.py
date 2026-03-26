"""
Abstract video stream / CCTV interface.

Implement this class to connect Tova to IP cameras or video feeds.
Supports: RTSP, ONVIF, HTTP streams, etc.
"""

from abc import ABC, abstractmethod


class BaseVideoStream(ABC):
    """Video stream provider for CCTV monitoring and analysis."""

    @abstractmethod
    async def connect_camera(
        self,
        camera_id: str,
        url: str,
        protocol: str = "rtsp",
        credentials: dict | None = None,
    ) -> dict:
        """Connect to a camera feed.

        Args:
            camera_id: Unique camera identifier
            url: Stream URL (e.g., rtsp://192.168.1.100:554/stream)
            protocol: Stream protocol (rtsp, http, onvif)
            credentials: Optional auth credentials

        Returns:
            {"camera_id": str, "status": str, "resolution": str}
        """
        ...

    @abstractmethod
    async def get_frame(self, camera_id: str) -> bytes:
        """Capture the latest frame from a camera.

        Returns:
            JPEG-encoded frame bytes
        """
        ...

    @abstractmethod
    async def list_cameras(self) -> list[dict]:
        """List all registered cameras.

        Returns:
            List of dicts: [{camera_id, name, url, status, location, last_frame_at}]
        """
        ...

    async def disconnect_camera(self, camera_id: str) -> bool:
        """Disconnect from a camera feed. Returns True if disconnected."""
        raise NotImplementedError

    async def start_recording(
        self,
        camera_id: str,
        duration_seconds: int = 0,
    ) -> dict:
        """Start recording from a camera.

        Args:
            duration_seconds: Recording duration (0 = continuous until stopped)

        Returns:
            {"recording_id": str, "status": str}
        """
        raise NotImplementedError

    async def stop_recording(self, recording_id: str) -> dict:
        """Stop an active recording.

        Returns:
            {"recording_id": str, "status": str, "file_path": str, "duration": int}
        """
        raise NotImplementedError

    async def get_recording(self, recording_id: str) -> dict:
        """Get recording metadata.

        Returns:
            {"recording_id": str, "camera_id": str, "file_path": str, "duration": int, "status": str}
        """
        raise NotImplementedError
