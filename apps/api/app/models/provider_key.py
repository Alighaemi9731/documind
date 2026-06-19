"""``provider_keys`` — encrypted BYOK credentials (ADR-0006/0007).

One row per ``(user_id, provider)`` holding a Fernet-encrypted key
(``ciphertext``), a non-secret ``key_fingerprint`` (sha256-only), the declared
``capabilities`` (from the ProviderSpec), and a monotonically increasing
``key_version`` bumped on replace. This is tenant data: RLS owner-only with NO
admin bypass (migration 0004). Only the fingerprint is ever surfaced; the
ciphertext is decrypted at the provider-call boundary and wrapped in the
redacting :class:`Secret`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class ProviderKey(Base, TimestampMixin):
    """An encrypted BYOK provider credential owned by exactly one user."""

    __tablename__ = "provider_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_provider_keys_user_provider"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary(), nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # JSON array of capability names (e.g. ["chat"]); read from the ProviderSpec.
    capabilities: Mapped[list[str]] = mapped_column(JSONB(), nullable=False, server_default="[]")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["ProviderKey"]
