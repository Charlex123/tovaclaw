"""
Credential encryption — Fernet symmetric encryption for secrets at rest.

Uses TOVA_ENCRYPTION_KEY env var. If not set, auto-generates a key
and persists it to ~/.tova/encryption.key (with 0600 permissions).

This ensures email passwords, API tokens, and other user secrets
are never stored in plaintext in SQLite or any other store.

Usage:
    from tova_core.crypto import encrypt, decrypt

    encrypted = encrypt("my-secret-password")
    original = decrypt(encrypted)
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_key() -> bytes:
    """Get or generate the encryption key."""
    # 1. Check env var
    env_key = os.environ.get("TOVA_ENCRYPTION_KEY", "")
    if env_key:
        # Accept raw Fernet key (44 base64 chars) or arbitrary string
        if len(env_key) == 44:
            try:
                base64.urlsafe_b64decode(env_key)
                return env_key.encode()
            except Exception:
                pass
        # Derive a Fernet-compatible key from arbitrary string
        import hashlib
        derived = hashlib.sha256(env_key.encode()).digest()
        return base64.urlsafe_b64encode(derived)

    # 2. Check persisted key file
    key_path = Path(os.environ.get("TOVA_STORE_DB", "~/.tova/tova.db")).expanduser().parent / "encryption.key"
    if key_path.exists():
        return key_path.read_bytes().strip()

    # 3. Generate and persist a new key
    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    os.chmod(key_path, 0o600)
    logger.info(f"Generated new encryption key at {key_path}")
    return key


def _get_fernet() -> Fernet:
    """Lazy-init the Fernet instance."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_key())
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns a base64-encoded ciphertext string.

    The result is safe to store in SQLite, JSON, or any text field.
    """
    f = _get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt(ciphertext: str) -> str:
    """Decrypt a previously encrypted string.

    Raises ValueError if the ciphertext is invalid or tampered with.
    """
    f = _get_fernet()
    try:
        plaintext = f.decrypt(ciphertext.encode("ascii"))
        return plaintext.decode("utf-8")
    except InvalidToken:
        raise ValueError("Failed to decrypt — invalid key or corrupted data")


def is_encrypted(value: str) -> bool:
    """Check if a string looks like a Fernet-encrypted token."""
    if not value or len(value) < 50:
        return False
    try:
        decoded = base64.urlsafe_b64decode(value + "==")
        # Fernet tokens start with version byte 0x80
        return len(decoded) > 0 and decoded[0] == 0x80
    except Exception:
        return False
