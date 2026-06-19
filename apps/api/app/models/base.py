"""Shared declarative base, mixins, and column helpers for all aggregates.

One ``Base`` (so a single ``Base.metadata`` feeds Alembic's autogenerate /
``target_metadata``), a ``TimestampMixin`` for ``created_at``/``updated_at``,
and a ``uuid_pk`` helper giving every aggregate a server-defaultable UUID PK.

Every module here imports without a live database connection.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base. ``Base.metadata`` is the Alembic target."""


def uuid_pk() -> Mapped[uuid.UUID]:
    """A UUID primary key column with a Python-side default.

    ``default=uuid.uuid4`` keeps inserts working even without a DB extension;
    the migration also sets a server default for rows created outside the ORM.
    """
    return mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` (UTC, DB-managed) to a model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["Base", "TimestampMixin", "uuid_pk"]
