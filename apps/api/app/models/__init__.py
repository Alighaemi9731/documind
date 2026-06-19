"""SQLAlchemy models package.

Importing this package registers every aggregate on ``Base.metadata`` so that
Alembic's ``target_metadata`` (and any ``create_all`` in tests) sees the full
schema. Import order matters only for FK-target resolution at mapper config
time, which SQLAlchemy resolves lazily, so plain alphabetical import is fine.
"""

from __future__ import annotations

from app.models.auth_identity import AuthIdentity
from app.models.base import Base, TimestampMixin
from app.models.invite import Invite
from app.models.project import Project
from app.models.refresh_token import RefreshToken
from app.models.system_settings import SystemSettings
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "AuthIdentity",
    "Invite",
    "Project",
    "RefreshToken",
    "SystemSettings",
    "User",
]
