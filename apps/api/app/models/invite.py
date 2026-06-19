"""``invites`` aggregate — single-use registration invites (invite mode).

Only the sha256 hash of the invite token is stored; the plaintext URL is shown
to the admin exactly once. ``consumed_at``/``consumed_by`` mark redemption.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import UserRole
from app.models.user import USER_ROLE_ENUM


class Invite(Base, TimestampMixin):
    """An invitation to register, optionally pinned to an email/role."""

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = uuid_pk()
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(CITEXT(), nullable=True)
    role: Mapped[UserRole] = mapped_column(USER_ROLE_ENUM, nullable=False, default=UserRole.user)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


__all__ = ["Invite"]
