"""
Creative providers — image generation, video generation, audio generation.

Abstract base classes that can be implemented with any backend:
- DALL-E, Stable Diffusion, Midjourney for images
- Runway, Pika, Sora for videos
- ElevenLabs, Murf for audio/voice

These are provider abstractions — the actual API keys and implementations
are plugged in by the host application.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeneratedImage:
    """Result of an image generation request."""
    url: str = ""
    base64_data: str = ""
    format: str = "png"
    width: int = 0
    height: int = 0
    prompt: str = ""
    revised_prompt: str = ""
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedVideo:
    """Result of a video generation request."""
    url: str = ""
    duration_seconds: float = 0
    width: int = 0
    height: int = 0
    format: str = "mp4"
    prompt: str = ""
    model: str = ""
    status: str = "completed"  # pending, processing, completed, failed
    job_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedAudio:
    """Result of an audio/speech generation request."""
    url: str = ""
    base64_data: str = ""
    duration_seconds: float = 0
    format: str = "mp3"
    voice: str = ""
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseImageGenerator(ABC):
    """Abstract image generation provider.

    Implement with DALL-E, Stable Diffusion, Midjourney, etc.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        style: str = "natural",
        quality: str = "standard",
        n: int = 1,
    ) -> list[GeneratedImage]:
        """Generate image(s) from a text prompt.

        Args:
            prompt: Description of the image to generate
            size: Image dimensions (e.g., "1024x1024", "1792x1024")
            style: Style hint: natural, vivid, artistic, photorealistic
            quality: standard or hd
            n: Number of images to generate

        Returns:
            List of generated images
        """
        ...

    @abstractmethod
    async def edit(
        self,
        image: bytes,
        prompt: str,
        mask: bytes | None = None,
    ) -> GeneratedImage:
        """Edit an existing image based on a prompt.

        Args:
            image: Original image bytes
            prompt: Description of the edit to make
            mask: Optional mask indicating which area to edit
        """
        ...

    @abstractmethod
    async def variations(
        self,
        image: bytes,
        n: int = 1,
        size: str = "1024x1024",
    ) -> list[GeneratedImage]:
        """Generate variations of an existing image."""
        ...


class BaseVideoGenerator(ABC):
    """Abstract video generation provider.

    Implement with Runway, Pika, Sora, Kling, etc.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
        style: str = "natural",
    ) -> GeneratedVideo:
        """Generate a video from a text prompt.

        Args:
            prompt: Description of the video to generate
            duration: Target duration in seconds
            aspect_ratio: Video aspect ratio
            style: Style hint

        Returns:
            Generated video (may be async — check status)
        """
        ...

    @abstractmethod
    async def image_to_video(
        self,
        image: bytes,
        prompt: str = "",
        duration: float = 5.0,
    ) -> GeneratedVideo:
        """Animate a still image into a video.

        Args:
            image: Source image bytes
            prompt: Motion/animation description
            duration: Target duration in seconds
        """
        ...

    @abstractmethod
    async def check_status(self, job_id: str) -> GeneratedVideo:
        """Check the status of an async video generation job."""
        ...


class BaseAudioGenerator(ABC):
    """Abstract audio/speech generation provider.

    Implement with ElevenLabs, OpenAI TTS, Google TTS, etc.
    """

    @abstractmethod
    async def text_to_speech(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        format: str = "mp3",
    ) -> GeneratedAudio:
        """Convert text to speech.

        Args:
            text: Text to speak
            voice: Voice identifier
            speed: Playback speed multiplier
            format: Output format (mp3, wav, ogg)
        """
        ...

    @abstractmethod
    async def list_voices(self) -> list[dict]:
        """List available voices."""
        ...
