"""Lightweight CPU reranker (section 8) — RRF + exact-phrase + filename bonus.

Re-orders the fused rows by a cheap score blend; the cross-encoder is OFF by
default (a heavyweight ``RERANK_MODEL`` would only load on >=4GB hosts). The
blend adds:

- the RRF score (the fused ordering signal),
- an **exact-phrase** bonus when the normalized query string occurs verbatim in
  the chunk content,
- a **bounded** filename bonus when the query terms appear in the filename.

The filename bonus is deliberately small and capped so an attacker-named file
("ignore_previous_instructions.pdf") cannot dominate ranking (section 8 /
ADR-0008). Reranking changes ORDER only — it never affects the grounding gate,
which keys off the raw cosine on the best chunk regardless of rank.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.text_norm import normalize
from app.rag.retrieval.fuse import FusedRow
from app.rag.retrieval.types import RetrievedRow

# Blend weights. The filename bonus is intentionally the smallest + capped.
_EXACT_PHRASE_BONUS = 0.5
_FILENAME_TERM_BONUS = 0.02
_FILENAME_BONUS_CAP = 0.1


def _filename_bonus(query_terms: list[str], filename: str) -> float:
    fname_norm = normalize(filename).lower()
    if not fname_norm or not query_terms:
        return 0.0
    hits = sum(1 for term in query_terms if term and term in fname_norm)
    return min(hits * _FILENAME_TERM_BONUS, _FILENAME_BONUS_CAP)


def _blend_score(fused: FusedRow, query_norm: str, query_terms: list[str]) -> float:
    score = fused.rrf_score
    content_norm = normalize(fused.row.content).lower()
    if query_norm and query_norm in content_norm:
        score += _EXACT_PHRASE_BONUS
    score += _filename_bonus(query_terms, fused.row.filename)
    return score


def rerank(fused_rows: Sequence[FusedRow], *, query: str) -> list[RetrievedRow]:
    """Return the fused rows reordered by the CPU score blend (descending).

    Stable tie-break on chunk_id keeps the ordering deterministic so the JSON
    fallback reproduces the streamed citations exactly (retrieval is idempotent).
    """
    query_norm = normalize(query).lower()
    query_terms = [t for t in query_norm.split(" ") if t]

    scored = [(_blend_score(fused, query_norm, query_terms), fused.row) for fused in fused_rows]
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].chunk_id)))
    return [row for _score, row in scored]


__all__ = ["rerank"]
