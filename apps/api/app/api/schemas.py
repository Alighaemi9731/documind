"""Pydantic request/response models for the Phase-1 API surface.

Shapes mirror ARCHITECTURE.md section 6 exactly. Secrets never appear here.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import DocumentErrorCode, DocumentStatus, UserRole, UserStatus

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
]
