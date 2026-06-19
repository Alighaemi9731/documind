"""Fernet/MultiFernet encryption for keys at rest (ADR-0006/0007).

``MASTER_KEY_FERNET`` may hold one or more comma-separated Fernet keys; the
first is the current (encrypting) key, the rest are retained for decryption
during rotation (MultiFernet). Decrypted material is returned inside the
Phase-1 redacting :class:`Secret` so it never leaks via repr/str/logging.
"""

from __future__ import annotations

import hashlib

from cryptography.fernet import Fernet, MultiFernet

from app.core.config import settings
from app.core.security import Secret


class KeyConfigError(RuntimeError):
    """Raised when ``MASTER_KEY_FERNET`` is missing or malformed."""


def _build_fernet() -> MultiFernet:
    raw = settings.master_key_fernet or ""
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise KeyConfigError("MASTER_KEY_FERNET is not configured; cannot encrypt/decrypt keys.")
    try:
        fernets = [Fernet(k.encode("utf-8")) for k in keys]
    except Exception as exc:  # noqa: BLE001
        raise KeyConfigError("MASTER_KEY_FERNET contains an invalid Fernet key.") from exc
    return MultiFernet(fernets)


def encrypt(plaintext: str) -> bytes:
    """Encrypt ``plaintext`` with the current Fernet key."""
    return _build_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> Secret:
    """Decrypt ``ciphertext`` (trying all configured keys) into a Secret."""
    plaintext = _build_fernet().decrypt(ciphertext).decode("utf-8")
    return Secret(plaintext)


def fingerprint(plaintext: str) -> str:
    """Non-secret fingerprint of a key, safe to store/display.

    A truncated SHA-256 only — it embeds NO raw key material (not even the last
    few characters), so it can never leak partial plaintext.
    """
    digest = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


__all__ = ["KeyConfigError", "encrypt", "decrypt", "fingerprint"]
