"""Keyword leg — tsvector(simple) full-text search over a tenant's chunks.

``content_tsv @@ websearch_to_tsquery('simple', :q_norm)`` ranked by
``ts_rank_cd`` descending, scoped to ``owner_id AND project_id``. The query
string is passed through the SAME :func:`app.core.text_norm.normalize` as ingest
(ADR-0004), so a Persian query with/without ZWNJ or diacritics matches the
stored tokens. ``websearch_to_tsquery`` never raises on arbitrary user input
(unlike ``to_tsquery``), so no sanitization branch is needed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import assert_guc
from app.core.text_norm import normalize

# Default fan-out of the keyword leg before fusion (mirrors RETRIEVE_TOPN).
KEYWORD_TOPN = 40


@dataclass(frozen=True)
class KeywordHit:
    """A keyword-leg hit: chunk id + ts_rank_cd + locators."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_no: int | None
    section_path: str | None
    chunk_index: int
    content: str
    rank: float


async def keyword_search(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    query: str,
    top_n: int = KEYWORD_TOPN,
) -> list[KeywordHit]:
    """Return the top-N keyword matches, scoped to the tenant + project.

    ``query`` is normalized here with the shared ``text_norm`` so ingest and
    query agree. An empty normalized query yields no rows.
    """
    await assert_guc(session, user_id)
    q_norm = normalize(query)
    if not q_norm:
        return []

    stmt = text(
        """
        SELECT
            c.id            AS chunk_id,
            c.document_id   AS document_id,
            d.filename      AS filename,
            c.page_no       AS page_no,
            c.section_path  AS section_path,
            c.chunk_index   AS chunk_index,
            c.content       AS content,
            ts_rank_cd(c.content_tsv, websearch_to_tsquery('simple', :q_norm)) AS rank
        FROM chunks AS c
        JOIN documents AS d ON d.id = c.document_id
        WHERE c.owner_id = :owner_id
          AND c.project_id = :project_id
          AND c.content_tsv @@ websearch_to_tsquery('simple', :q_norm)
        ORDER BY rank DESC
        LIMIT :top_n
        """
    ).bindparams(
        bindparam("q_norm", value=q_norm),
        bindparam("owner_id", value=user_id),
        bindparam("project_id", value=project_id),
        bindparam("top_n", value=top_n),
    )
    result = await session.execute(stmt)
    rows = result.mappings().all()
    return [
        KeywordHit(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            filename=row["filename"],
            page_no=row["page_no"],
            section_path=row["section_path"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            rank=float(row["rank"]),
        )
        for row in rows
    ]


__all__ = ["KeywordHit", "KEYWORD_TOPN", "keyword_search"]
