"""BYOK keystore — encrypt/store/load/list/delete per-user provider keys.

Secrets never leave the server: pasted keys are Fernet-encrypted at rest
(:mod:`app.providers.keystore.crypto`), the stored ``key_fingerprint`` is a
sha256-only digest (no raw material), and :func:`load_user_key` returns the
decrypted value wrapped in the redacting :class:`Secret`. ``list_user_keys``
returns metadata ONLY (provider, fingerprint, validity, checked_at) — never the
ciphertext or plaintext.

Operates on the caller-supplied tenant session: ``provider_keys`` is RLS
owner-only, so the session must already be scoped to ``user_id``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Secret
from app.models.provider_key import ProviderKey
from app.providers import registry
from app.providers.keystore import crypto


@dataclass(frozen=True)
class KeyMetadata:
    """Non-secret metadata about a stored BYOK key (safe to return)."""

    provider: str
    fingerprint: str
    valid: bool
    checked_at: datetime | None


def _capabilities_for(provider: str) -> list[str]:
    """The capability names a provider offers, from its ProviderSpec."""
    try:
        spec = registry.get_spec(provider)
    except KeyError:
        return []
    return [c.value for c in spec.capabilities]


async def save_user_key(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
    raw_key: str,
) -> ProviderKey:
    """Encrypt + upsert a BYOK key for ``(user_id, provider)``.

    Stores the ciphertext, the sha256-only fingerprint, and the capabilities
    from the ProviderSpec. On replace, bumps ``key_version`` and re-activates
    the row. The raw key is never logged and never persisted in plaintext.
    """
    ciphertext = crypto.encrypt(raw_key)
    fingerprint = crypto.fingerprint(raw_key)
    capabilities = _capabilities_for(provider)

    result = await session.execute(
        select(ProviderKey).where(ProviderKey.user_id == user_id, ProviderKey.provider == provider)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ProviderKey(
            user_id=user_id,
            provider=provider,
            ciphertext=ciphertext,
            key_fingerprint=fingerprint,
            key_version=1,
            capabilities=capabilities,
            is_active=True,
        )
        session.add(row)
    else:
        row.ciphertext = ciphertext
        row.key_fingerprint = fingerprint
        row.key_version = row.key_version + 1
        row.capabilities = capabilities
        row.is_active = True
    await session.flush()
    return row


async def load_user_key(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
) -> Secret | None:
    """Decrypt the active BYOK key for ``(user_id, provider)`` into a Secret.

    Returns ``None`` if there is no active key for that provider.
    """
    result = await session.execute(
        select(ProviderKey).where(
            ProviderKey.user_id == user_id,
            ProviderKey.provider == provider,
            ProviderKey.is_active.is_(True),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return crypto.decrypt(row.ciphertext)


async def list_user_keys(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[KeyMetadata]:
    """Return metadata for the user's stored keys (NEVER the secret).

    Validity here is the stored ``is_active`` flag (set at save time after a
    health check); ``checked_at`` is the row's ``updated_at`` (last save/validate).
    """
    result = await session.execute(select(ProviderKey).where(ProviderKey.user_id == user_id))
    rows = result.scalars().all()
    return [
        KeyMetadata(
            provider=row.provider,
            fingerprint=row.key_fingerprint,
            valid=row.is_active,
            checked_at=row.updated_at,
        )
        for row in rows
    ]


async def delete_user_key(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
) -> bool:
    """Delete the BYOK key for ``(user_id, provider)``. Returns True if removed."""
    result = await session.execute(
        select(ProviderKey).where(ProviderKey.user_id == user_id, ProviderKey.provider == provider)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.flush()
    return True


__all__ = [
    "KeyMetadata",
    "save_user_key",
    "load_user_key",
    "list_user_keys",
    "delete_user_key",
]
