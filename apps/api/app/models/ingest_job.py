"""``ingest_jobs`` — the durable DB-backed work queue (ADR-0005).

One row per document to ingest. The in-process asyncio worker claims a row with
``SELECT ... FOR UPDATE SKIP LOCKED`` and a lease (``locked_at`` /
``lease_expires_at``); a crashed worker's lease expires and the job becomes
re-claimable. ``last_cursor`` resumes a rate-limited (TRANSIENT) embed stage
without losing progress. ``owner_id`` lets the worker set the tenant GUC from
``job.owner_id`` on its own session (ADR-0002).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class IngestJob(Base, TimestampMixin):
    """A unit of ingestion work for one document."""

    __tablename__ = "ingest_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)

    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_cursor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)


__all__ = ["IngestJob"]
