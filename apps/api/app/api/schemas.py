"""Pydantic request/response models for the Phase-1 API surface.

Shapes mirror ARCHITECTURE.md section 6 exactly. Secrets never appear here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    Capability,
    DocumentErrorCode,
    DocumentStatus,
    UserRole,
    UserStatus,
)

# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    invite_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserPublic(BaseModel):
    """The user object embedded in auth responses and returned by /me."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    status: UserStatus


class TokenResponse(BaseModel):
    """200 body for login / successful open registration."""

    access_token: str
    expires_in: int
    user: UserPublic


class PendingResponse(BaseModel):
    """202 body for approval-mode registration."""

    status: str = "pending"


class MeResponse(BaseModel):
    """GET /api/auth/me — section 6 shape (provider/quota stubbed in Phase 1)."""

    id: uuid.UUID
    email: str
    role: UserRole
    status: UserStatus
    active_provider: str | None = None
    has_byok: dict[str, bool] = Field(default_factory=dict)
    quota: dict[str, int | None] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class ProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dim: int | None
    embedding_normalized: bool | None


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #


class UploadResult(BaseModel):
    """One element of the 201 array returned by the upload endpoint."""

    filename: str
    document_id: uuid.UUID | None = None
    status: DocumentStatus | None = None
    dedupe: bool = False
    error_code: DocumentErrorCode | None = None


class DocumentPublic(BaseModel):
    """Status-poll shape for a single document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime: str
    size_bytes: int
    page_count: int | None
    status: DocumentStatus
    status_detail: str | None
    error_code: DocumentErrorCode | None
    chunk_count: int
    embedding_model: str | None
    embedding_dim: int | None


# --------------------------------------------------------------------------- #
# Query (RAG)
# --------------------------------------------------------------------------- #


class QueryRequest(BaseModel):
    """POST /api/projects/{id}/query body (section 6)."""

    question: str = Field(min_length=1, max_length=8000)
    stream: bool = True
    conversation_id: uuid.UUID | None = None


# --------------------------------------------------------------------------- #
# Public config
# --------------------------------------------------------------------------- #


class ConfigResponse(BaseModel):
    """GET /api/config — UI bootstrap (max upload + registration mode)."""

    max_upload_mb: int
    registration_mode: str


# --------------------------------------------------------------------------- #
# Settings — BYOK keys + provider selection (write-only secrets; NEVER returned)
# --------------------------------------------------------------------------- #


class KeyMetadataPublic(BaseModel):
    """GET /api/settings/keys element — metadata ONLY (never the secret)."""

    provider: str
    fingerprint: str
    valid: bool
    checked_at: datetime | None = None


class KeyCreateRequest(BaseModel):
    """POST /api/settings/keys — write-only; the key never comes back."""

    provider: str
    api_key: str = Field(min_length=1, max_length=4096)


class KeyCreateResponse(BaseModel):
    """POST /api/settings/keys — fingerprint + validity only (no secret)."""

    provider: str
    fingerprint: str
    valid: bool


class ModelOption(BaseModel):
    """A model a provider offers for a capability (settings UI)."""

    model: str
    dim: int = 0
    normalized: bool = False
    max_input_tokens: int = 0


class ProviderInfo(BaseModel):
    """GET /api/settings/providers element — capabilities + models (no secrets)."""

    id: str
    label: str
    capabilities: list[str]
    requires_byok: bool
    chat: ModelOption | None = None
    embedding: ModelOption | None = None
    key_format_hint: str | None = None
    has_byok: bool = False


class SelectionPublic(BaseModel):
    """The user's current per-capability provider+model selection."""

    capability: str
    provider: str
    model: str


class ProvidersResponse(BaseModel):
    """GET /api/settings/providers — available providers + current selections."""

    providers: list[ProviderInfo]
    selections: list[SelectionPublic]


class SelectionRequest(BaseModel):
    """PUT /api/settings/providers — set the provider+model for a capability."""

    capability: Capability
    provider: str
    model: str = Field(min_length=1, max_length=128)


# --------------------------------------------------------------------------- #
# Admin — users, quota, usage, invites, keys metadata, operator key
# --------------------------------------------------------------------------- #


class AdminUserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    status: UserStatus
    created_at: datetime


class AdminUserList(BaseModel):
    users: list[AdminUserPublic]
    page: int
    total: int


class QuotaPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    monthly_token_limit: int | None = None
    requests_per_day: int | None = None
    hard_disabled: bool = False


class QuotaUpdate(BaseModel):
    monthly_token_limit: int | None = None
    requests_per_day: int | None = None
    hard_disabled: bool | None = None


class InviteCreateRequest(BaseModel):
    email: EmailStr | None = None
    role: UserRole = UserRole.user


class InviteCreateResponse(BaseModel):
    """The invite token is shown ONCE here (copy-the-URL delivery, ADR-0001)."""

    id: uuid.UUID
    token: str
    role: UserRole
    expires_at: datetime


class InvitePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    role: UserRole
    expires_at: datetime
    consumed_at: datetime | None


class UsagePoint(BaseModel):
    bucket: str
    tokens_in: int
    tokens_out: int


class UsageResponse(BaseModel):
    series: list[UsagePoint]


class OperatorKeyPublic(BaseModel):
    provider: str
    fingerprint: str
    key_version: int


class OperatorKeyRotateRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)


__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "UserPublic",
    "TokenResponse",
    "PendingResponse",
    "MeResponse",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectPublic",
    "UploadResult",
    "DocumentPublic",
    "QueryRequest",
    "ConfigResponse",
    "KeyMetadataPublic",
    "KeyCreateRequest",
    "KeyCreateResponse",
    "ModelOption",
    "ProviderInfo",
    "SelectionPublic",
    "ProvidersResponse",
    "SelectionRequest",
    "AdminUserPublic",
    "AdminUserList",
    "QuotaPublic",
    "QuotaUpdate",
    "InviteCreateRequest",
    "InviteCreateResponse",
    "InvitePublic",
    "UsagePoint",
    "UsageResponse",
    "OperatorKeyPublic",
    "OperatorKeyRotateRequest",
]
