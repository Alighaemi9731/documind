"""SQLAlchemy models package.

Importing this package registers every aggregate on ``Base.metadata`` so that
Alembic's ``target_metadata`` (and any ``create_all`` in tests) sees the full
schema. Import order matters only for FK-target resolution at mapper config
time, which SQLAlchemy resolves lazily, so plain alphabetical import is fine.
"""

from __future__ import annotations

from app.models.auth_identity import AuthIdentity
from app.models.base import Base, TimestampMixin
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.ingest_job import IngestJob
from app.models.invite import Invite
from app.models.message import Message
from app.models.operator_default import OperatorDefault
from app.models.project import Project
from app.models.provider_key import ProviderKey
from app.models.provider_selection import ProviderSelection
from app.models.refresh_token import RefreshToken
from app.models.system_settings import SystemSettings
from app.models.usage import UsageEvent, UserMonthlyUsage, UserQuota
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "AuthIdentity",
    "Chunk",
    "Conversation",
    "Document",
    "IngestJob",
    "Invite",
    "Message",
    "OperatorDefault",
    "Project",
    "ProviderKey",
    "ProviderSelection",
    "RefreshToken",
    "SystemSettings",
    "UsageEvent",
    "UserMonthlyUsage",
    "UserQuota",
    "User",
]
