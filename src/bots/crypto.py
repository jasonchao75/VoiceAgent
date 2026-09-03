"""Fernet encryption helpers for optional bot-level API key storage."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class StorageKeyError(RuntimeError):
    """Raised when the master storage key is missing, malformed, or mismatched."""


class BotKeyCipher:
    """Encrypt and decrypt bot-level provider keys at rest.

    The master key lives only in the VOICE_AGENT_STORAGE_KEY environment
    variable; losing it makes every stored key permanently undecryptable.
    """

    def __init__(self, master_key: str) -> None:
        """Create a cipher from a Fernet master key.

        Args:
            master_key: URL-safe base64 Fernet key from the environment.

        Raises:
            StorageKeyError: If the key is not a valid Fernet key.
        """
        try:
            self._fernet = Fernet(master_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise StorageKeyError("VOICE_AGENT_STORAGE_KEY is not a valid Fernet key") from exc

    @classmethod
    def from_env(cls) -> BotKeyCipher | None:
        """Build a cipher from the environment, or None when key storage is disabled.

        Raises:
            StorageKeyError: If a configured key is malformed; fail closed on typos.
        """
        raw = os.getenv("VOICE_AGENT_STORAGE_KEY", "").strip()
        if not raw:
            return None
        return cls(raw)

    def encrypt(self, secret: SecretStr) -> str:
        """Encrypt one provider key into an ASCII ciphertext token."""
        return self._fernet.encrypt(secret.get_secret_value().encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> SecretStr:
        """Decrypt one stored ciphertext token back into memory.

        Raises:
            StorageKeyError: If the master key does not match the ciphertext.
        """
        try:
            plaintext = self._fernet.decrypt(token.encode("ascii"))
        except InvalidToken as exc:
            raise StorageKeyError(
                "Stored bot API keys cannot be decrypted with the configured storage key"
            ) from exc
        return SecretStr(plaintext.decode("utf-8"))
