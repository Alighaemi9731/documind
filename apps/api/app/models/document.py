"""``documents`` aggregate — one uploaded file per project (ARCHITECTURE.md 5).

``owner_id`` is denormalized (copied from the project) so RLS and ``TenantScope``
can isolate documents without a join, and so chunks can inherit the stamp. The
``(project_id, content_sha256)`` unique constraint implements per-project
dedupe. Status / error_code drive the ingestion state machine.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import DocumentErrorCode, DocumentStatus

# Reuse one named PG enum across model + migration so values stay canonical.
DOCUMENT_STATUS_ENUM = SAEnum(
    DocumentStatus,
    name="document_status",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)
DOCUMENT_ERROR_CODE_ENUM = SAEnum(
    DocumentErrorCode,
    name="document_error_code",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class Document(Base, TimestampMixin):
    """An uploaded file undergoing or having completed ingestion."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("project_id", "content_sha256", name="uq_documents_project_sha256"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized tenant key (copied from the owning project, never client).
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[DocumentStatus] = mapped_column(
        DOCUMENT_STATUS_ENUM,
        nullable=False,
        default=DocumentStatus.queued,
        server_default=DocumentStatus.queued.value,
    )
    status_detail: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_code: Mapped[DocumentErrorCode | None] = mapped_column(
        DOCUMENT_ERROR_CODE_ENUM, nullable=True
    )

    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)


__all__ = ["Document", "DOCUMENT_STATUS_ENUM", "DOCUMENT_ERROR_CODE_ENUM"]
