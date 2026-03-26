"""
Notes & Summarization tools.

Enable agents to create notes, summarize content, and extract key points.
"""

from __future__ import annotations

import logging
from datetime import datetime
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


def build_notes_tools(store: BaseStore) -> list:
    """Build notes and summarization tools using the provider pattern."""

    @tool
    async def create_note(
        user_id: str,
        title: str,
        content: str,
        tags: str = "",
        source_type: str = "manual",
    ) -> dict:
        """Create a new note for the user.

        Args:
            user_id: The user who owns this note
            title: Note title
            content: Note content (supports markdown)
            tags: Comma-separated tags
            source_type: Source: manual, summary, email, meeting, web
        """
        try:
            note_data = {
                "title": title,
                "content": content,
                "summary": "",
                "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
                "source_type": source_type,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            note_id = await store.save_note(user_id, note_data)
            return {"success": True, "id": note_id, "title": title}
        except NotImplementedError:
            return {"error": "Note storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_notes(
        user_id: str,
        limit: int = 20,
    ) -> dict:
        """List the user's saved notes.

        Args:
            user_id: The user whose notes to list
            limit: Maximum number of notes to return
        """
        try:
            notes = await store.list_notes(user_id, limit=limit)
            return {
                "notes": [
                    {
                        "id": n.get("id", ""),
                        "title": n.get("title", ""),
                        "summary": n.get("summary", ""),
                        "tags": n.get("tags", []),
                        "source_type": n.get("source_type", ""),
                        "created_at": n.get("created_at", ""),
                    }
                    for n in notes
                ],
                "count": len(notes),
            }
        except NotImplementedError:
            return {"notes": [], "count": 0}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def summarize_text(
        text: str,
        style: str = "concise",
    ) -> dict:
        """Summarize the provided text content.

        The agent itself generates the summary using its LLM capabilities.
        This tool structures the request.

        Args:
            text: The text content to summarize
            style: Summary style: concise, detailed, bullet_points, executive
        """
        # The agent handles summarization directly via its LLM
        # This tool provides structure for the request
        word_count = len(text.split())
        return {
            "original_length": word_count,
            "style": style,
            "text_to_summarize": text[:10000],  # Limit for context
            "instruction": f"Please summarize the above text in a {style} style.",
        }

    @tool
    async def extract_key_points(text: str) -> dict:
        """Extract key points and action items from text.

        Args:
            text: The text to analyze for key points
        """
        word_count = len(text.split())
        return {
            "original_length": word_count,
            "text_to_analyze": text[:10000],
            "instruction": (
                "Extract from the above text:\n"
                "1. Key points (main ideas)\n"
                "2. Action items (things to do)\n"
                "3. Important dates/deadlines mentioned\n"
                "4. Key people/entities mentioned"
            ),
        }

    @tool
    async def summarize_document(
        user_id: str,
        note_id: str,
    ) -> dict:
        """Summarize an existing note/document by its ID.

        Args:
            user_id: The user who owns the note
            note_id: The note ID to summarize
        """
        try:
            note = await store.get_note(note_id)
            if not note:
                return {"error": f"Note {note_id} not found"}

            return {
                "title": note.get("title", ""),
                "content_length": len(note.get("content", "")),
                "text_to_summarize": note.get("content", "")[:10000],
                "instruction": "Please summarize this document concisely.",
            }
        except NotImplementedError:
            return {"error": "Note storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    return [create_note, list_notes, summarize_text, extract_key_points, summarize_document]
