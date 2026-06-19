"""``chunks`` aggregate — a normalized, embedded slice of a document.

Tenant keys (``owner_id``, ``project_id``) and ``embedding_dim`` are
denormalized/stamped at insert time by the store layer (never client supplied)
so RLS isolation and the per-dim partial HNSW index work without a join. The
embedding is an unbounded ``halfvec`` (ADR-0003) holding vectors of any
dimension. ``content_tsv`` is a generated/stored ``tsvector('simple')`` column
(ADR-0004) for the keyword leg of hybrid retrieval; the store normalizes
``content`` with ``text_norm`` before insert so ingest and query agree.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import Computed, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class Chunk(Base):
    """A retrievable chunk with its embedding + generated keyword tsvector."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized tenant keys, stamped by the store (NOT NULL, never client).
    project_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    content: Mapped[str] = mapped_column(Text(), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Unbounded halfvec (ADR-0003); a single column holds any dimensionality.
    embedding: Mapped[list[float]] = mapped_column(HALFVEC(), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)

    # Generated, STORED tsvector('simple') for the keyword leg (ADR-0004).
    content_tsv: Mapped[str] = mapped_column(
        TSVECTOR(),
        Computed("to_tsvector('simple', content)", persisted=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = ["Chunk"]
