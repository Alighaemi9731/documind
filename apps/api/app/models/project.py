"""``projects`` aggregate — a tenant-owned container of documents.

Phase-1 columns plus the Phase-2 embedding-pin columns pulled forward
(nullable for now). ``owner_id`` is the tenant key used by ``TenantScope`` and
the RLS policy; deleting a user cascades to their projects.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class Project(Base, TimestampMixin):
    """A project owned by exactly one user (``owner_id``, NOT NULL)."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # Phase-2 embedding pin (immutable post-creation except via re-embed).
    # Nullable now; populated when the provider slice lands in Phase 2.
    embedding_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_normalized: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


__all__ = ["Project"]
