"""``conversations`` aggregate — a chat thread over a project's corpus (ADR-0017).

A conversation groups the user + assistant :class:`~app.models.message.Message`
turns. ``owner_id`` is the tenant key used by ``TenantScope`` and the owner-only
RLS policy (content table, NO admin bypass — ADR-0002); ``project_id`` scopes the
thread to one project. Persistence is real in v1 so the SSE ``done`` event can
carry a durable ``message_id`` even though retrieval is single-turn (ADR-0017).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class Conversation(Base, TimestampMixin):
    """A chat thread owned by one user, scoped to one project."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)


__all__ = ["Conversation"]
