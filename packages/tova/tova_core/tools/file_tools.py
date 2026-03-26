"""
File organization tools.

Enable agents to read, organize, and manage files.
"""

from __future__ import annotations

import hashlib
import logging
from langchain_core.tools import tool

from tova_core.providers.file_store import BaseFileStore

logger = logging.getLogger(__name__)


def build_file_tools(file_store: BaseFileStore) -> list:
    """Build file organization tools using the provider pattern."""

    @tool
    async def list_files(
        path_prefix: str,
        limit: int = 50,
    ) -> dict:
        """List files in a directory/storage path.

        Args:
            path_prefix: Path prefix to list (e.g., "user_123/documents/")
            limit: Maximum files to return
        """
        try:
            files = await file_store.list_files(prefix=path_prefix, limit=limit)
            return {
                "files": [
                    {
                        "path": f.get("path", ""),
                        "size": f.get("size", 0),
                        "content_type": f.get("content_type", ""),
                        "created_at": f.get("created_at", ""),
                    }
                    for f in files
                ],
                "count": len(files),
                "prefix": path_prefix,
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def organize_files(path_prefix: str) -> dict:
        """Analyze files in a path and suggest organization.

        Categorizes files by type and suggests a folder structure.

        Args:
            path_prefix: Path to analyze
        """
        try:
            files = await file_store.list_files(prefix=path_prefix, limit=100)

            categories = {}
            for f in files:
                ct = f.get("content_type", "unknown")
                if "image" in ct:
                    cat = "images"
                elif "pdf" in ct or "document" in ct:
                    cat = "documents"
                elif "spreadsheet" in ct or "csv" in ct or "excel" in ct:
                    cat = "spreadsheets"
                elif "video" in ct:
                    cat = "videos"
                elif "audio" in ct:
                    cat = "audio"
                elif "text" in ct or "json" in ct or "xml" in ct:
                    cat = "text_data"
                else:
                    cat = "other"

                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(f.get("path", ""))

            return {
                "total_files": len(files),
                "categories": {
                    cat: {"count": len(paths), "files": paths[:5]}
                    for cat, paths in categories.items()
                },
                "instruction": (
                    "Based on the file analysis, suggest:\n"
                    "1. Recommended folder structure\n"
                    "2. Files that could be renamed for clarity\n"
                    "3. Any duplicates or unnecessary files"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def find_duplicates(path_prefix: str) -> dict:
        """Scan files for duplicates based on content hash.

        Args:
            path_prefix: Path to scan for duplicates
        """
        try:
            files = await file_store.list_files(prefix=path_prefix, limit=200)

            hashes = {}
            duplicates = []

            for f in files:
                path = f.get("path", "")
                try:
                    content = await file_store.download(path)
                    content_hash = hashlib.md5(content).hexdigest()

                    if content_hash in hashes:
                        duplicates.append({
                            "original": hashes[content_hash],
                            "duplicate": path,
                            "size": f.get("size", 0),
                        })
                    else:
                        hashes[content_hash] = path
                except Exception:
                    continue

            return {
                "total_scanned": len(files),
                "duplicates_found": len(duplicates),
                "duplicates": duplicates,
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def extract_file_content(file_path: str) -> dict:
        """Extract text content from a file (PDF, DOCX, TXT, etc.).

        Args:
            file_path: Path to the file in storage
        """
        try:
            content = await file_store.download(file_path)
            files_info = await file_store.list_files(prefix=file_path, limit=1)
            content_type = ""
            if files_info:
                content_type = files_info[0].get("content_type", "")

            # Try to decode as text
            try:
                text = content.decode("utf-8")
                return {
                    "path": file_path,
                    "content_type": content_type,
                    "text": text[:10000],
                    "size_bytes": len(content),
                    "truncated": len(content) > 10000,
                }
            except UnicodeDecodeError:
                return {
                    "path": file_path,
                    "content_type": content_type,
                    "size_bytes": len(content),
                    "note": "Binary file — use dataset ingestion for PDF/DOCX extraction",
                }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def rename_suggestions(path_prefix: str) -> dict:
        """Analyze file names and suggest better names.

        Args:
            path_prefix: Path to analyze
        """
        try:
            files = await file_store.list_files(prefix=path_prefix, limit=50)
            file_names = [f.get("path", "").split("/")[-1] for f in files]

            return {
                "files": file_names,
                "count": len(file_names),
                "instruction": (
                    "Review these file names and suggest improvements:\n"
                    "1. Replace generic names (IMG_001, Document1) with descriptive ones\n"
                    "2. Add dates where appropriate\n"
                    "3. Use consistent naming conventions\n"
                    "4. Group related files with common prefixes"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    return [list_files, organize_files, find_duplicates, extract_file_content, rename_suggestions]
