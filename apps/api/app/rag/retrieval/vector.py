"""Vector leg — pgvector cosine search over a tenant's chunks (section 8).

Embeds the (already ``text_norm``-normalized) query via the resolver's embedding
provider, then runs ``embedding <=> :q`` (cosine distance) ascending, scoped to
``owner_id AND project_id AND embedding_dim``. Returns the top-N rows with the
**raw cosine similarity** (``1 - cosine_distance``) per row — the grounding gate
(ADR-0008) needs this exact number, so we return it rather than the RRF score.

The query embedding goes through the SAME resolver path as ingest, so a missing
key / dim mismatch surfaces the resolver's typed errors. Tests inject a
deterministic ``FakeEmbeddingProvider`` via ``resolver.set_embedding_override``,
so no real network call happens.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import assert_guc
from app.models.enums import Capability
from app.providers import resolver

# Default fan-out of the vector leg before fusion (RETRIEVE_TOPN, section 8).
RETRIEVE_TOPN = 40


@dataclass(frozen=True)
class VectorHit:
    """A vector-leg hit: chunk id + raw cosine similarity + locators."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_no: int | None
    section_path: str | None
    chunk_index: int
    content: str
    score_cosine: float


async def embed_query_vector(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    query_norm: str,
) -> tuple[list[float], int]:
    """Resolve the embedding provider + embed the normalized query.

    Returns ``(vector, embedding_dim)``. The dim comes from the project pin via
    the resolver, so the vector leg can scope to ``embedding_dim`` exactly.
    """
    resolved = await resolver.resolve(session, user_id, Capability.embedding, project_id=project_id)
    vector = resolved.adapter.embed_query(query_norm, model=resolved.model)
    return vector, resolved.dim


async def vector_search(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    query_norm: str,
    top_n: int = RETRIEVE_TOPN,
) -> list[VectorHit]:
    """Embed the query and return the top-N nearest chunks (cosine), scoped.

    The result is ordered by ascending cosine distance; each row carries the
    raw cosine SIMILARITY (``1 - distance``) so the grounding gate has a
    calibrated anchor (ADR-0008). The query is joined to ``documents`` only to
    read ``filename`` for the citation locator; both tables are RLS-scoped.
    """
    await assert_guc(session, user_id)
    vector, dim = await embed_query_vector(
        session, user_id=user_id, project_id=project_id, query_norm=query_norm
    )

    # ``dim`` is an int from the resolver (project pin), so it is safe to inline
    # as the halfvec typmod literal — a Postgres type modifier CANNOT be a bind
    # parameter. ``int(dim)`` guards against any non-integer slipping through.
    dim_lit = int(dim)
    stmt = text(
        f"""
        SELECT
            c.id            AS chunk_id,
            c.document_id   AS document_id,
            d.filename      AS filename,
            c.page_no       AS page_no,
            c.section_path  AS section_path,
            c.chunk_index   AS chunk_index,
            c.content       AS content,
            1 - ((c.embedding::halfvec({dim_lit})) <=> :q) AS score_cosine
        FROM chunks AS c
        JOIN documents AS d ON d.id = c.document_id
        WHERE c.owner_id = :owner_id
          AND c.project_id = :project_id
          AND c.embedding_dim = :dim_val
        ORDER BY (c.embedding::halfvec({dim_lit})) <=> :q ASC
        LIMIT :top_n
        """
    ).bindparams(
        bindparam("q", value=vector, type_=HALFVEC()),
        bindparam("dim_val", value=dim_lit),
        bindparam("owner_id", value=user_id),
        bindparam("project_id", value=project_id),
        bindparam("top_n", value=top_n),
    )
    result = await session.execute(stmt)
    rows = result.mappings().all()
    return [
        VectorHit(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            filename=row["filename"],
            page_no=row["page_no"],
            section_path=row["section_path"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            score_cosine=float(row["score_cosine"]),
        )
        for row in rows
    ]


__all__ = ["VectorHit", "RETRIEVE_TOPN", "vector_search", "embed_query_vector"]
