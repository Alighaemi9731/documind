"""``users`` aggregate — the account root for every tenant."""

from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import UserRole, UserStatus

# Reuse one named PG enum across models/migration so values stay canonical.
USER_ROLE_ENUM = SAEnum(
    UserRole,
    name="user_role",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)
USER_STATUS_ENUM = SAEnum(
    UserStatus,
    name="user_status",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class User(Base, TimestampMixin):
    """A registered account. ``email`` is CITEXT-unique and NFC-normalized.

    ``token_version`` is bumped to invalidate every outstanding access JWT
    (instant global logout / disable); ``status`` gates authentication.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(USER_ROLE_ENUM, nullable=False, default=UserRole.user)
    status: Mapped[UserStatus] = mapped_column(
        USER_STATUS_ENUM, nullable=False, default=UserStatus.active
    )
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registration_source: Mapped[str | None] = mapped_column(String(64), nullable=True)


__all__ = ["User", "USER_ROLE_ENUM", "USER_STATUS_ENUM"]
