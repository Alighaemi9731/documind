"""``messages`` aggregate — one chat turn (user or assistant) (ADR-0017).

Each row is a single turn in a :class:`~app.models.conversation.Conversation`.
The ``user`` turn holds the question; the ``assistant`` turn holds the answer
plus the authoritative ``grounded`` flag, the resolved ``provider``, and the
**validated** ``citations`` (the canonical Citation[] persisted with the answer,
already filtered to the retrieved chunk-id set). ``owner_id`` / ``project_id``
are denormalized tenant keys (never client supplied) so RLS + ``TenantScope``
isolate messages without a join. ``messages`` is a tenant CONTENT table:
owner-only RLS, NO admin bypass (ADR-0002).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk
from app.models.enums import MessageRole

# One named PG enum reused across model + migration so values stay canonical.
MESSAGE_ROLE_ENUM = SAEnum(
    MessageRole,
    name="message_role",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class Message(Base):
    """A single user/assistant turn, with citations + grounded on assistant rows."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized tenant keys, stamped server-side (NOT NULL, never client).
    owner_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)

    role: Mapped[MessageRole] = mapped_column(MESSAGE_ROLE_ENUM, nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)

    # Assistant-only: the authoritative grounded flag (nullable on user turns).
    grounded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # The validated Citation[] persisted with the assistant answer.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]", default=list
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = ["Message", "MESSAGE_ROLE_ENUM"]
