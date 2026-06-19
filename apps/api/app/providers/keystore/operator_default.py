"""Seed + load the encrypted operator-default key (ADR-0007).

``seed_operator_default`` upserts the encrypted row (idempotent: re-seeding
overwrites with a fresh fingerprint/ciphertext). ``load_operator_key`` decrypts
the stored row into a redacting :class:`Secret`. Both operate on the metadata
(non-tenant) session — ``operator_default`` is operator config, not tenant data.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Secret
from app.models.enums import Provider
from app.models.operator_default import OperatorDefault
from app.providers.keystore import crypto


class OperatorKeyNotConfigured(RuntimeError):
    """Raised when no operator-default key row exists for a provider."""


async def seed_operator_default(
    session: AsyncSession,
    key: str,
    *,
    provider: str = Provider.google.value,
) -> OperatorDefault:
    """Encrypt + upsert the operator key for ``provider``.

    Seeded from ``OPERATOR_DEFAULT_GEMINI_KEY`` on first run; admin-rotatable
    thereafter. The DB row is the source of truth once seeded.
    """
    ciphertext = crypto.encrypt(key)
    fp = crypto.fingerprint(key)

    result = await session.execute(
        select(OperatorDefault).where(OperatorDefault.provider == provider)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = OperatorDefault(
            provider=provider,
            ciphertext=ciphertext,
            key_fingerprint=fp,
            key_version=1,
        )
        session.add(row)
    else:
        row.ciphertext = ciphertext
        row.key_fingerprint = fp
        row.key_version = row.key_version + 1
    await session.flush()
    return row


async def load_operator_key(
    session: AsyncSession,
    *,
    provider: str = Provider.google.value,
) -> Secret:
    """Decrypt the operator key for ``provider`` into a redacting Secret."""
    result = await session.execute(
        select(OperatorDefault).where(OperatorDefault.provider == provider)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise OperatorKeyNotConfigured(f"No operator-default key configured for {provider!r}.")
    return crypto.decrypt(row.ciphertext)


__all__ = [
    "OperatorKeyNotConfigured",
    "seed_operator_default",
    "load_operator_key",
]
