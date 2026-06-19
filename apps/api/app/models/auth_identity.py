"""``auth_identities`` aggregate — login credentials, OAuth-ready.

A user has one identity per ``(provider, provider_subject)``. The password
identity uses ``provider='password'`` and stores an argon2id ``password_hash``;
future OAuth identities store ``provider_subject`` and leave the hash NULL —
no core migration required to add them.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk

# The password identity uses this provider literal. Stored as plain text (not
# the Provider enum) because auth identities include 'password', which is not
# a model Provider.
PASSWORD_PROVIDER = "password"


class AuthIdentity(Base, TimestampMixin):
    """A credential linking a login method to a :class:`User`."""

    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_identity_provider_subject"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)


__all__ = ["AuthIdentity", "PASSWORD_PROVIDER"]
