"""Canonical shared enums (single source of truth).

These mirror ARCHITECTURE.md section 6 / ADR-0013 exactly. Every subsystem
(models, API handlers, migrations, frontend types) derives from these rather
than redefining them. Do not add ad-hoc values here without a contract change.

All enums subclass ``str`` so values serialize as their literal string form in
JSON and in the database.
"""

from __future__ import annotations

import enum


class UserRole(enum.StrEnum):
    """Account role. ``admin`` unlocks the admin dashboard and RLS bypass."""

    user = "user"
    admin = "admin"


class UserStatus(enum.StrEnum):
    """Account lifecycle state. Only ``active`` may authenticate."""

    active = "active"
    pending = "pending"
    disabled = "disabled"


class RegistrationMode(enum.StrEnum):
    """How new accounts are created (system_settings.registration_mode)."""

    open = "open"
    approval = "approval"
    invite = "invite"


class Provider(enum.StrEnum):
    """Supported model providers. Defined now for reuse in later phases."""

    openai = "openai"
    anthropic = "anthropic"
    google = "google"
    groq = "groq"
    local_bge_m3 = "local_bge_m3"


class Capability(enum.StrEnum):
    """A provider capability (singular form is canonical)."""

    chat = "chat"
    embedding = "embedding"


class KeySource(enum.StrEnum):
    """Whether a provider call used the shared operator key or a BYOK key."""

    shared = "shared"
    byok = "byok"


class DocumentStatus(enum.StrEnum):
    """Ingestion lifecycle of a document (ARCHITECTURE.md section 6).

    State machine: ``queued -> parsing -> chunking -> embedding -> ready``;
    any non-terminal state may transition to ``failed`` with a
    :class:`DocumentErrorCode`. Terminal states are ``ready`` and ``failed``.
    """

    queued = "queued"
    parsing = "parsing"
    chunking = "chunking"
    embedding = "embedding"
    ready = "ready"
    failed = "failed"


class DocumentErrorCode(enum.StrEnum):
    """Typed terminal-failure reasons recorded on ``documents.error_code``."""

    OVERSIZE = "OVERSIZE"
    BAD_TYPE = "BAD_TYPE"
    DECOMPRESSION_BOMB = "DECOMPRESSION_BOMB"
    ENCRYPTED_PDF = "ENCRYPTED_PDF"
    NO_TEXT = "NO_TEXT"
    PARSE_ERROR = "PARSE_ERROR"
    EMBED_ERROR = "EMBED_ERROR"
    TOO_MANY_CHUNKS = "TOO_MANY_CHUNKS"


__all__ = [
    "UserRole",
    "UserStatus",
    "RegistrationMode",
    "Provider",
    "Capability",
    "KeySource",
    "DocumentStatus",
    "DocumentErrorCode",
]
