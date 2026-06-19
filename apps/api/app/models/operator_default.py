"""``operator_default`` — the encrypted shared operator key row (ADR-0007).

One row per provider holding a Fernet-encrypted key (``ciphertext``), seeded
from ``OPERATOR_DEFAULT_GEMINI_KEY`` on first run and admin-rotatable in-app.
Only the non-secret ``key_fingerprint`` is ever surfaced; the ciphertext is
decrypted with ``MASTER_KEY_FERNET`` exactly at the provider-call boundary.

This is operator metadata, NOT tenant content, so it is not RLS-scoped; it is
only ever read on the metadata/admin session path.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class OperatorDefault(Base, TimestampMixin):
    """Encrypted operator-default provider key (one row per provider)."""

    __tablename__ = "operator_default"

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary(), nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


__all__ = ["OperatorDefault"]
