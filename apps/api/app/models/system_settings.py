"""``system_settings`` — a singleton row holding install-wide runtime config.

Seeded from env on first run, admin-flippable thereafter. A single row is
enforced by a CHECK constraint on a fixed ``id`` value.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import RegistrationMode

# Fixed PK of the one and only settings row.
SINGLETON_ID = 1

REGISTRATION_MODE_ENUM = SAEnum(
    RegistrationMode,
    name="registration_mode",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class SystemSettings(Base, TimestampMixin):
    """Install-wide settings; exactly one row (``id == SINGLETON_ID``)."""

    __tablename__ = "system_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_system_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SINGLETON_ID)
    registration_mode: Mapped[RegistrationMode] = mapped_column(
        REGISTRATION_MODE_ENUM,
        nullable=False,
        default=RegistrationMode.open,
    )
    default_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    signups_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    branding: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


__all__ = ["SystemSettings", "SINGLETON_ID", "REGISTRATION_MODE_ENUM"]
