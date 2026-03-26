"""
Abstract file/blob storage interface.

Implement this class to connect Tova to your file storage.
Supports any storage: GCS, S3, Azure Blob, local filesystem.
"""

from abc import ABC, abstractmethod


class BaseFileStore(ABC):
    """File storage provider for document uploads, CCTV recordings, etc.

    Path convention: {user_id}/{feature}/{filename}
    """

    @abstractmethod
    async def upload(
        self,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """Upload a file.

        Args:
            path: Storage path (e.g., "user_123/datasets/report.pdf")
            content: File content as bytes
            content_type: MIME type
            metadata: Optional metadata tags

        Returns:
            Public or signed URL for the uploaded file
        """
        ...

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download a file's content.

        Args:
            path: Storage path

        Returns:
            File content as bytes
        """
        ...

    @abstractmethod
    async def list_files(
        self,
        prefix: str,
        limit: int = 100,
    ) -> list[dict]:
        """List files under a path prefix.

        Args:
            prefix: Path prefix to filter (e.g., "user_123/datasets/")
            limit: Maximum number of results

        Returns:
            List of dicts: [{path, size, content_type, created_at, metadata}]
        """
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a file. Returns True if deleted."""
        ...

    async def get_signed_url(
        self,
        path: str,
        expires_minutes: int = 60,
    ) -> str:
        """Generate a time-limited signed URL for a file.

        Args:
            path: Storage path
            expires_minutes: URL expiration time in minutes

        Returns:
            Signed URL string
        """
        raise NotImplementedError

    async def exists(self, path: str) -> bool:
        """Check if a file exists at the given path."""
        try:
            await self.download(path)
            return True
        except Exception:
            return False
