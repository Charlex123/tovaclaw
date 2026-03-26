"""
Local filesystem file store — zero-config file management.

Stores files on the local filesystem with metadata tracking.
For production, replace with S3FileStore, GCSFileStore, etc.

Usage:
    # Default (stores in ~/.tova/files/):
    store = LocalFileStore()

    # Custom path:
    store = LocalFileStore(base_path="/data/tova/files")

    # Upload:
    url = await store.upload("user123/docs/report.pdf", pdf_bytes, "application/pdf")

    # Download:
    content = await store.download("user123/docs/report.pdf")

    # List:
    files = await store.list_files("user123/docs/")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tova_core.providers.file_store import BaseFileStore

logger = logging.getLogger(__name__)


class LocalFileStore(BaseFileStore):
    """Local filesystem-backed file storage.

    Files stored at: {base_path}/{path}
    Metadata stored at: {base_path}/.meta/{path}.json

    Path convention: {user_id}/{feature}/{filename}
    """

    def __init__(
        self,
        base_path: str | None = None,
    ):
        self.base_path = Path(
            base_path or os.environ.get("TOVA_FILE_STORE_PATH", "~/.tova/files")
        ).expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._meta_path = self.base_path / ".meta"
        self._meta_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """Resolve a storage path to an absolute filesystem path."""
        resolved = (self.base_path / path).resolve()
        # Prevent path traversal
        if not str(resolved).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Invalid path: {path}")
        return resolved

    def _meta_file(self, path: str) -> Path:
        """Get the metadata file path for a storage path."""
        safe = path.replace("/", "__").replace("\\", "__")
        return self._meta_path / f"{safe}.json"

    async def upload(
        self,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """Upload a file to local storage."""
        file_path = self._resolve(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path.write_bytes(content)

        # Write metadata
        meta = {
            "path": path,
            "content_type": content_type,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self._meta_file(path).write_text(json.dumps(meta, indent=2))

        logger.info(f"File stored: {path} ({len(content)} bytes)")
        return f"file://{file_path}"

    async def download(self, path: str) -> bytes:
        """Download a file from local storage."""
        file_path = self._resolve(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_bytes()

    async def list_files(
        self,
        prefix: str,
        limit: int = 100,
    ) -> list[dict]:
        """List files under a path prefix."""
        search_dir = self._resolve(prefix)
        if not search_dir.exists():
            return []

        files = []
        if search_dir.is_file():
            # Exact file match
            meta = self._load_meta(prefix)
            files.append(meta)
        else:
            # Directory listing
            for item in sorted(search_dir.rglob("*")):
                if item.is_file() and not str(item).startswith(str(self._meta_path)):
                    rel_path = str(item.relative_to(self.base_path))
                    meta = self._load_meta(rel_path)
                    files.append(meta)
                    if len(files) >= limit:
                        break

        return files

    def _load_meta(self, path: str) -> dict:
        """Load metadata for a file, or generate from filesystem."""
        meta_file = self._meta_file(path)
        if meta_file.exists():
            try:
                return json.loads(meta_file.read_text())
            except json.JSONDecodeError:
                pass

        # Generate from filesystem
        file_path = self._resolve(path)
        if file_path.exists():
            stat = file_path.stat()
            return {
                "path": path,
                "content_type": _guess_content_type(path),
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(
                    stat.st_ctime, tz=timezone.utc
                ).isoformat(),
                "metadata": {},
            }
        return {"path": path, "size": 0, "content_type": "", "metadata": {}}

    async def delete(self, path: str) -> bool:
        """Delete a file from local storage."""
        file_path = self._resolve(path)
        if not file_path.exists():
            return False

        file_path.unlink()

        # Remove metadata
        meta_file = self._meta_file(path)
        if meta_file.exists():
            meta_file.unlink()

        logger.info(f"File deleted: {path}")
        return True

    async def exists(self, path: str) -> bool:
        """Check if a file exists."""
        return self._resolve(path).exists()

    async def get_signed_url(
        self,
        path: str,
        expires_minutes: int = 60,
    ) -> str:
        """For local files, returns the file:// path (no signing needed)."""
        file_path = self._resolve(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return f"file://{file_path}"


def _guess_content_type(path: str) -> str:
    """Guess MIME type from file extension."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    types = {
        "pdf": "application/pdf",
        "json": "application/json",
        "csv": "text/csv",
        "txt": "text/plain",
        "md": "text/markdown",
        "html": "text/html",
        "xml": "application/xml",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "mp4": "video/mp4",
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "zip": "application/zip",
    }
    return types.get(ext, "application/octet-stream")
