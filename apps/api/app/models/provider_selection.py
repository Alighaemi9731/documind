"""``provider_selections`` — per-user, per-capability chosen provider+model.

One row per ``(user_id, capability)`` recording which provider/model the user
selected for that capability (e.g. chat=openai/gpt-4o-mini). The resolver reads
this to decide the BYOK branch; absence means fall back to the operator default.
Owner-scoped tenant table (RLS owner-only, NO admin bypass).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class ProviderSelection(Base, TimestampMixin):
    """The per-capability provider+model a user has chosen."""

    __tablename__ = "provider_selections"
    __table_args__ = (
        UniqueConstraint("user_id", "capability", name="uq_provider_selections_user_capability"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capability: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)


__all__ = ["ProviderSelection"]
