"""Usage + quota models (ADR-0009, ARCHITECTURE.md section 10).

- ``usage_events`` is APPEND-ONLY: one row per provider call, attributing the
  ``key_source`` (shared|byok) and ``capability`` (chat|embedding) plus token
  counts. Indexed on ``(user_id, created_at)`` for time-series admin queries.
- ``user_monthly_usage`` is a per-user rolling aggregate keyed by ``period``
  (``YYYY-MM``) used for O(1) quota pre-check via SELECT ... FOR UPDATE.
- ``user_quota`` holds the per-user shared-key limits (nullable -> install
  default) and a hard-disable kill switch.

All three are owner-scoped tenant tables (RLS owner-only, NO admin bypass).
``usage_events.project_id`` is SET NULL on project delete so history survives.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class UsageEvent(Base):
    """Append-only record of one provider call (ADR-0009)."""

    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    key_source: Mapped[str] = mapped_column(String(16), nullable=False)
    capability: Mapped[str] = mapped_column(String(16), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class UserMonthlyUsage(Base):
    """Per-user, per-period rolling token counter for O(1) quota pre-check."""

    __tablename__ = "user_monthly_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "period", name="uq_user_monthly_usage_user_period"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Period like "2026-06"; the rolling window the quota is enforced against.
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserQuota(Base):
    """Per-user shared-key quota knobs (admin-editable)."""

    __tablename__ = "user_quota"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Nullable -> fall back to the install default (settings.default_quota).
    monthly_token_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requests_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hard_disabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


__all__ = ["UsageEvent", "UserMonthlyUsage", "UserQuota"]
