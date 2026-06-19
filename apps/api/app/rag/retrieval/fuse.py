"""Reciprocal Rank Fusion (RRF, k=60) over the two ranked legs (section 8).

RRF fuses two incomparable score scales (cosine distance vs ts_rank_cd) by rank
alone: each chunk's fused score is ``sum(1 / (k + rank_i))`` over the legs it
appears in (rank is 1-based). The output is a fused ordering of
:class:`RetrievedRow`s. The vector leg's **raw cosine similarity** is carried
through onto each row (``score_cosine``) but is NEVER used as the fusion score —
the grounding gate keys off ``score_cosine`` directly, not the RRF score
(ADR-0008).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.rag.retrieval.keyword import KeywordHit
from app.rag.retrieval.types import RetrievedRow
from app.rag.retrieval.vector import VectorHit

# RRF constant (section 8). Larger k flattens the contribution of top ranks.
RRF_K = 60


@dataclass(frozen=True)
class FusedRow:
    """A retrieved row plus its (fusion-only) RRF score, for the reranker."""

    row: RetrievedRow
    rrf_score: float


def _rrf_contribution(rank_zero_based: int, k: int) -> float:
    # rank is 1-based in the RRF formula: 1 / (k + rank).
    return 1.0 / (k + rank_zero_based + 1)


def fuse_rrf(
    vector_hits: Sequence[VectorHit],
    keyword_hits: Sequence[KeywordHit],
    *,
    k: int = RRF_K,
) -> list[FusedRow]:
    """Fuse the two ranked legs into one ordering by RRF score (descending).

    Ties (equal RRF score) break deterministically by chunk_id so the ordering
    is stable across runs (important for idempotent JSON fallback). The vector
    leg's raw cosine is preserved on the merged row.
    """
    scores: dict[uuid.UUID, float] = {}
    rows: dict[uuid.UUID, RetrievedRow] = {}

    for rank, hit in enumerate(vector_hits):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + _rrf_contribution(rank, k)
        rows[hit.chunk_id] = RetrievedRow(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            filename=hit.filename,
            page_no=hit.page_no,
            section_path=hit.section_path,
            chunk_index=hit.chunk_index,
            content=hit.content,
            score_cosine=hit.score_cosine,
        )

    for rank, khit in enumerate(keyword_hits):
        scores[khit.chunk_id] = scores.get(khit.chunk_id, 0.0) + _rrf_contribution(rank, k)
        if khit.chunk_id not in rows:
            rows[khit.chunk_id] = RetrievedRow(
                chunk_id=khit.chunk_id,
                document_id=khit.document_id,
                filename=khit.filename,
                page_no=khit.page_no,
                section_path=khit.section_path,
                chunk_index=khit.chunk_index,
                content=khit.content,
                score_cosine=None,
            )

    ordered = sorted(
        rows.values(),
        key=lambda r: (-scores[r.chunk_id], str(r.chunk_id)),
    )
    return [FusedRow(row=r, rrf_score=scores[r.chunk_id]) for r in ordered]


__all__ = ["RRF_K", "FusedRow", "fuse_rrf"]
