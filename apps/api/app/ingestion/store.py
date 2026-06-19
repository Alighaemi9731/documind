"""Chunk persistence (ARCHITECTURE.md section 7, ADR-0003).

The store is the ONLY writer of chunk rows. It STAMPS ``owner_id``,
``project_id`` and ``embedding_dim`` from the owning document/project — never
from anything client-supplied — and rejects any vector whose length does not
equal the project's pinned ``embedding_dim`` (ADR-0015). Re-embed is implemented
as delete-then-insert keyed by ``document_id``.

The per-dimension partial HNSW index is built lazily (deferred per ADR-0003) by
:func:`ensure_hnsw_index`, never at migration time.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import CursorResult, delete, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import assert_guc
from app.ingestion.chunker import Chunk as ChunkData
from app.models.chunk import Chunk
from app.models.document import Document


class DimensionMismatch(ValueError):
    """A vector length does not match the project's pinned embedding_dim."""


async def delete_document_chunks(
    session: AsyncSession, *, document_id: uuid.UUID, owner_id: uuid.UUID
) -> int:
    """Delete all chunks for a document (re-embed / reprocess). Returns count."""
    await assert_guc(session, owner_id)
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(Chunk).where(Chunk.document_id == document_id, Chunk.owner_id == owner_id)
        ),
    )
    return int(result.rowcount or 0)


async def store_chunks(
    session: AsyncSession,
    *,
    document: Document,
    chunks: Sequence[ChunkData],
    embeddings: Sequence[Sequence[float]],
    project_id: uuid.UUID,
    owner_id: uuid.UUID,
    embedding_dim: int,
) -> int:
    """Insert chunk rows, stamping tenant keys + dim. Returns rows written.

    ``owner_id`` / ``project_id`` / ``embedding_dim`` are derived from the owning
    document and project (never the client). Each embedding must have exactly
    ``embedding_dim`` components or :class:`DimensionMismatch` is raised before
    any row is written (the surrounding transaction rolls back).
    """
    await assert_guc(session, owner_id)
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch.")

    rows: list[Chunk] = []
    for chunk, vector in zip(chunks, embeddings, strict=True):
        if len(vector) != embedding_dim:
            raise DimensionMismatch(
                f"Embedding has {len(vector)} dims; project is pinned to {embedding_dim}."
            )
        rows.append(
            Chunk(
                document_id=document.id,
                project_id=project_id,
                owner_id=owner_id,
                chunk_index=chunk.chunk_index,
                page_no=chunk.page_no,
                section_path=chunk.section_path,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                content=chunk.normalized_content,
                token_count=chunk.token_count,
                embedding=list(vector),
                embedding_dim=embedding_dim,
            )
        )

    session.add_all(rows)
    await session.flush()

    await session.execute(
        update(Document)
        .where(Document.id == document.id)
        .values(chunk_count=len(rows), embedding_dim=embedding_dim)
    )
    return len(rows)


async def ensure_hnsw_index(session: AsyncSession, dim: int) -> None:
    """Build the per-dim partial HNSW index lazily (ADR-0003), if absent.

    Uses ``CREATE INDEX CONCURRENTLY IF NOT EXISTS`` so an existing index is a
    no-op and the build does not hold a heavy lock. CONCURRENTLY cannot run
    inside a transaction block, so the caller must invoke this on an
    autocommit/raw connection outside the ingest transaction.
    """
    name = f"chunks_emb_{dim}_hnsw"
    await session.execute(
        text(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} "
            f"ON chunks USING hnsw ((embedding::halfvec({dim})) halfvec_cosine_ops) "
            f"WITH (m = 16, ef_construction = 64) "
            f"WHERE embedding_dim = {dim}"
        )
    )


__all__ = [
    "DimensionMismatch",
    "store_chunks",
    "delete_document_chunks",
    "ensure_hnsw_index",
]
