"""
Creative tools — image generation, video generation, audio generation.

Gives agents the ability to create visual and audio content:
- Generate images from text descriptions
- Create videos from prompts or images
- Generate speech/audio from text
- Edit and create variations of existing images

Works with any creative provider implementation (DALL-E, Stable Diffusion,
Runway, ElevenLabs, etc.).
"""

from __future__ import annotations

import logging
from datetime import datetime

from langchain_core.tools import tool

from tova_core.providers.creative import (
    BaseImageGenerator,
    BaseVideoGenerator,
    BaseAudioGenerator,
)
from tova_core.providers.file_store import BaseFileStore

logger = logging.getLogger(__name__)


def build_image_tools(
    image_generator: BaseImageGenerator,
    file_store: BaseFileStore | None = None,
) -> list:
    """Build image generation tools."""

    @tool
    async def generate_image(
        user_id: str,
        prompt: str,
        size: str = "1024x1024",
        style: str = "natural",
        quality: str = "standard",
        count: int = 1,
        save_as: str = "",
    ) -> dict:
        """Generate an image from a text description using AI.

        Creates high-quality images from any description. Can generate:
        - Logos, icons, brand assets
        - Illustrations, artwork, digital art
        - Photorealistic scenes and objects
        - Charts, diagrams, infographics (stylized)
        - Social media graphics, banners, thumbnails
        - Product mockups, concept art

        Args:
            user_id: Image owner
            prompt: Detailed description of the image to generate.
                    Be specific: subject, style, lighting, colors, mood, composition.
                    Example: "A modern minimalist logo for a tech startup called 'Nexus',
                    blue and white color scheme, clean geometric shapes"
            size: Image dimensions: "1024x1024" (square), "1792x1024" (landscape), "1024x1792" (portrait)
            style: Visual style: natural, vivid, artistic, photorealistic, cartoon, sketch, watercolor
            quality: "standard" (fast) or "hd" (high detail)
            count: Number of images to generate (1-4)
            save_as: Optional filename to save in workspace (e.g., "logo.png")
        """
        try:
            images = await image_generator.generate(
                prompt=prompt,
                size=size,
                style=style,
                quality=quality,
                n=min(count, 4),
            )

            results = []
            for i, img in enumerate(images):
                result = {
                    "url": img.url,
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "prompt": img.revised_prompt or prompt,
                    "model": img.model,
                }

                # Save to file store if requested
                if save_as and file_store and img.base64_data:
                    import base64
                    fname = save_as if count == 1 else f"{save_as.rsplit('.', 1)[0]}_{i+1}.{img.format}"
                    path = f"{user_id}/workspace/images/{fname}"
                    await file_store.upload(
                        path=path,
                        content=base64.b64decode(img.base64_data),
                        content_type=f"image/{img.format}",
                        metadata={"prompt": prompt, "generated_by": "tova"},
                    )
                    result["saved_path"] = path

                results.append(result)

            return {
                "success": True,
                "images": results,
                "count": len(results),
                "message": f"Generated {len(results)} image(s).",
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def edit_image(
        user_id: str,
        file_path: str,
        edit_prompt: str,
        save_as: str = "",
    ) -> dict:
        """Edit an existing image using AI.

        Modify, enhance, or transform an existing image based on a text description.

        Args:
            user_id: Image owner
            file_path: Path to the existing image in workspace
            edit_prompt: Description of the edit (e.g., "remove the background",
                        "make it look like a painting", "change the sky to sunset")
            save_as: Optional filename for the edited image
        """
        try:
            full_path = file_path if file_path.startswith(user_id) else f"{user_id}/{file_path}"

            if not file_store:
                return {"error": "File store not configured — cannot access images"}

            image_bytes = await file_store.download(full_path)
            result = await image_generator.edit(image=image_bytes, prompt=edit_prompt)

            output = {
                "url": result.url,
                "format": result.format,
                "prompt": edit_prompt,
            }

            if save_as and result.base64_data:
                import base64
                save_path = f"{user_id}/workspace/images/{save_as}"
                await file_store.upload(
                    path=save_path,
                    content=base64.b64decode(result.base64_data),
                    content_type=f"image/{result.format}",
                    metadata={"edit_prompt": edit_prompt, "source": full_path},
                )
                output["saved_path"] = save_path

            return {"success": True, **output}
        except Exception as e:
            return {"error": str(e)}

    return [generate_image, edit_image]


def build_video_tools(
    video_generator: BaseVideoGenerator,
    file_store: BaseFileStore | None = None,
) -> list:
    """Build video generation tools."""

    @tool
    async def generate_video(
        user_id: str,
        prompt: str,
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
        style: str = "natural",
    ) -> dict:
        """Generate a video from a text description using AI.

        Creates short video clips from text descriptions. Can generate:
        - Product demos, explainer clips
        - Social media content (reels, shorts, stories)
        - Animations, motion graphics
        - Scene visualizations
        - Marketing/advertising clips

        Video generation is async — use check_video_status to poll for completion.

        Args:
            user_id: Video owner
            prompt: Detailed description of the video scene. Include:
                    subject, action, camera movement, lighting, style.
                    Example: "Aerial drone shot slowly circling a modern glass skyscraper
                    at golden hour, with city traffic below, cinematic look"
            duration: Target duration in seconds (typically 3-15)
            aspect_ratio: "16:9" (landscape), "9:16" (portrait/mobile), "1:1" (square)
            style: natural, cinematic, animated, artistic, slow_motion
        """
        try:
            video = await video_generator.generate(
                prompt=prompt,
                duration=duration,
                aspect_ratio=aspect_ratio,
                style=style,
            )

            return {
                "success": True,
                "status": video.status,
                "job_id": video.job_id,
                "url": video.url if video.status == "completed" else None,
                "duration": video.duration_seconds,
                "format": video.format,
                "model": video.model,
                "message": (
                    f"Video generated successfully!" if video.status == "completed"
                    else f"Video is being generated. Job ID: {video.job_id}. Use check_video_status to track progress."
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def check_video_status(
        job_id: str,
    ) -> dict:
        """Check the status of a video generation job.

        Args:
            job_id: The job ID returned from generate_video
        """
        try:
            video = await video_generator.check_status(job_id)
            return {
                "job_id": job_id,
                "status": video.status,
                "url": video.url if video.status == "completed" else None,
                "duration": video.duration_seconds,
                "message": (
                    f"Video ready: {video.url}" if video.status == "completed"
                    else f"Video status: {video.status}"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def image_to_video(
        user_id: str,
        file_path: str,
        prompt: str = "",
        duration: float = 5.0,
    ) -> dict:
        """Animate a still image into a video.

        Takes an existing image and brings it to life with motion.

        Args:
            user_id: Image owner
            file_path: Path to the source image
            prompt: Motion/animation description (e.g., "camera slowly zooms in",
                    "the person smiles and waves", "leaves blow in the wind")
            duration: Target video duration in seconds
        """
        try:
            full_path = file_path if file_path.startswith(user_id) else f"{user_id}/{file_path}"

            if not file_store:
                return {"error": "File store not configured — cannot access images"}

            image_bytes = await file_store.download(full_path)
            video = await video_generator.image_to_video(
                image=image_bytes,
                prompt=prompt,
                duration=duration,
            )

            return {
                "success": True,
                "status": video.status,
                "job_id": video.job_id,
                "url": video.url if video.status == "completed" else None,
                "source_image": full_path,
                "message": (
                    f"Video created from image!" if video.status == "completed"
                    else f"Animating image... Job ID: {video.job_id}"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    return [generate_video, check_video_status, image_to_video]


def build_audio_tools(audio_generator: BaseAudioGenerator) -> list:
    """Build audio/speech generation tools."""

    @tool
    async def text_to_speech(
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        format: str = "mp3",
    ) -> dict:
        """Convert text to natural-sounding speech using AI.

        Create voiceovers, narrations, podcasts, audiobook segments, or any spoken audio.

        Args:
            text: The text to convert to speech
            voice: Voice to use (use list_voices to see options)
            speed: Speed multiplier (0.5=slow, 1.0=normal, 2.0=fast)
            format: Output format: mp3, wav, ogg
        """
        try:
            audio = await audio_generator.text_to_speech(
                text=text, voice=voice, speed=speed, format=format,
            )
            return {
                "success": True,
                "url": audio.url,
                "duration_seconds": audio.duration_seconds,
                "voice": audio.voice,
                "format": audio.format,
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_voices() -> dict:
        """List all available AI voices for text-to-speech."""
        try:
            voices = await audio_generator.list_voices()
            return {"voices": voices, "count": len(voices)}
        except Exception as e:
            return {"error": str(e)}

    return [text_to_speech, list_voices]
