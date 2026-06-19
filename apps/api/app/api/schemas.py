"""Pydantic request/response models for the Phase-1 API surface.

Shapes mirror ARCHITECTURE.md section 6 exactly. Secrets never appear here.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import (
    Capability,
    DocumentErrorCode,
    DocumentStatus,
    RegistrationMode,
    UserRole,
    UserStatus,
)

# Branding defaults (used by GET /api/config and GET /api/admin/settings when the
# system_settings.branding JSON is empty / partially populated). The accent is a
# sensible Apple-style blue; logo defaults to None (text wordmark).
DEFAULT_APP_NAME = "DocuMind"
DEFAULT_ACCENT_COLOR = "#0071E3"
# Accent allow-list, mirrored EXACTLY by the client's normalizeAccent
# (apps/web/lib/branding.tsx): a 3- or 6-digit hex, OR a Tailwind-style HSL
# channel triple ("221 83% 53%") consumed by hsl(var(--accent)). Both forms are
# free of CSS-breaking characters, so neither can escape the custom-property
# value the client applies via the CSSOM. Anything else is rejected (422 on
# write) / dropped to the default (on read).
_HEX_COLOR_RE = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"
_HSL_TRIPLE_RE = r"^\d{1,3}\s+\d{1,3}%\s+\d{1,3}%$"


def _is_safe_accent(value: str) -> bool:
    """True iff ``value`` is an allow-listed accent color (hex or HSL triple)."""
    return bool(re.match(_HEX_COLOR_RE, value) or re.match(_HSL_TRIPLE_RE, value))


def _safe_relative_logo(value: str) -> str | None:
    """Return ``value`` iff it is a relative, same-origin path; else ``None``.

    Rejects schemes (``http:``), protocol-relative (``//host``), and bare hosts —
    anything that could introduce a third-party origin under the strict CSP.
    """
    if value == "":
        return None
    if "://" in value or value.startswith("//") or ":" in value.split("/")[0]:
        return None
    if not value.startswith("/"):
        return None
    return value


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


class BrandingPublic(BaseModel):
    """Branding surfaced to the UI (public config + admin settings).

    ``app_name`` is plain text and MUST be rendered as text by the client (never
    as HTML). ``logo_url`` is always a relative, same-origin path or None.
    """

    app_name: str = DEFAULT_APP_NAME
    accent_color: str = DEFAULT_ACCENT_COLOR
    logo_url: str | None = None


def branding_from_stored(stored: dict[str, object] | None) -> BrandingPublic:
    """Build a :class:`BrandingPublic` from the stored branding JSON.

    Missing/empty fields fall back to defaults so the UI always has a complete,
    safe branding payload even on a fresh install or a partial admin write.
    """
    data = stored or {}
    app_name = data.get("app_name")
    accent = data.get("accent_color")
    logo = data.get("logo_url")
    # Re-validate on READ too: even though writes are validated, a value that
    # predates a tightened rule (or a hand-edited row) must never reach the DOM.
    safe_accent = (
        accent if isinstance(accent, str) and _is_safe_accent(accent) else DEFAULT_ACCENT_COLOR
    )
    safe_logo = _safe_relative_logo(logo) if isinstance(logo, str) else None
    return BrandingPublic(
        app_name=app_name if isinstance(app_name, str) and app_name.strip() else DEFAULT_APP_NAME,
        accent_color=safe_accent,
        logo_url=safe_logo,
    )


class ConfigResponse(BaseModel):
    """GET /api/config — UI bootstrap (upload cap, registration mode, branding)."""

    max_upload_mb: int
    registration_mode: str
    branding: BrandingPublic


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


# --------------------------------------------------------------------------- #
# Admin — system settings + branding
# --------------------------------------------------------------------------- #


class BrandingUpdate(BaseModel):
    """Subset-write of branding. Each field validated and stored as plain text.

    All fields optional so the admin can PATCH-style update one knob at a time.
    """

    model_config = ConfigDict(extra="forbid")

    app_name: str | None = Field(default=None, min_length=1, max_length=80)
    accent_color: str | None = Field(default=None, max_length=32)
    logo_url: str | None = Field(default=None, max_length=512)

    @field_validator("app_name")
    @classmethod
    def _clean_app_name(cls, value: str | None) -> str | None:
        """Strip control characters and collapse whitespace (defense-in-depth).

        ``app_name`` is rendered as plain text (never HTML), so this is cosmetic
        hardening: a stray newline / NUL can't change meaning, only spacing.
        """
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", "".join(ch for ch in value if ch.isprintable())).strip()
        if not cleaned:
            raise ValueError("app_name must contain visible characters")
        return cleaned

    @field_validator("accent_color")
    @classmethod
    def _validate_accent(cls, value: str | None) -> str | None:
        """Accept only an allow-listed accent (hex or HSL triple), matching the
        client's normalizeAccent. Keeps client and server in lockstep so a value
        the UI accepts is never rejected here (and vice-versa)."""
        if value is None or value == "":
            return None
        if not _is_safe_accent(value):
            raise ValueError("accent_color must be a #hex or 'H S% L%' value")
        return value

    @field_validator("logo_url")
    @classmethod
    def _validate_logo_url(cls, value: str | None) -> str | None:
        """Only a relative, same-origin path (or empty) is allowed.

        Absolute/external URLs are rejected to avoid mixed-content and to keep
        the strict CSP (no third-party origins) intact. Empty string clears it.
        """
        if value is None or value == "":
            return None
        safe = _safe_relative_logo(value)
        if safe is None:
            raise ValueError("logo_url must be a relative, same-origin path")
        return safe


class AdminSettingsPublic(BaseModel):
    """GET/PUT /api/admin/settings — install-wide knobs + branding."""

    registration_mode: RegistrationMode
    default_provider: str
    signups_enabled: bool
    default_monthly_token_limit: int
    branding: BrandingPublic


class AdminSettingsUpdate(BaseModel):
    """PUT /api/admin/settings — any subset of the install-wide knobs."""

    model_config = ConfigDict(extra="forbid")

    registration_mode: RegistrationMode | None = None
    default_provider: str | None = Field(default=None, min_length=1, max_length=32)
    signups_enabled: bool | None = None
    default_monthly_token_limit: int | None = Field(default=None, ge=0)
    branding: BrandingUpdate | None = None


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
    "BrandingPublic",
    "branding_from_stored",
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
    "BrandingUpdate",
    "AdminSettingsPublic",
    "AdminSettingsUpdate",
]
