"""
Abstract authentication interface.

Implement this class to verify user tokens/sessions.
"""

from abc import ABC, abstractmethod


class BaseAuth(ABC):
    """Auth provider — verifies user tokens and extracts user identity.

    Implement with your own auth system (Firebase, Auth0, Supabase,
    custom JWT, session tokens, etc.).
    """

    @abstractmethod
    async def verify_token(self, token: str) -> str:
        """Verify an authentication token and return the user ID.

        Args:
            token: The auth token (JWT, session token, API key, etc.)

        Returns:
            The authenticated user's ID.

        Raises:
            Exception: If the token is invalid, expired, or verification fails.
        """
        ...
