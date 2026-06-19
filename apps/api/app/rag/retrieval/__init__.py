"""Hybrid retrieval (ARCHITECTURE.md section 8): vector + keyword fused by RRF.

The legs return ranked :class:`RetrievedRow`s; :func:`fuse_rrf` produces a fused
ordering; :func:`rerank` applies a CPU score-blend. The vector leg additionally
exposes the **raw cosine similarity** of each row, which the grounding gate
(ADR-0008) uses as its sole trust anchor — never the RRF score.
"""

from __future__ import annotations

from app.rag.retrieval.fuse import fuse_rrf
from app.rag.retrieval.keyword import keyword_search
from app.rag.retrieval.rerank import rerank
from app.rag.retrieval.types import RetrievedRow
from app.rag.retrieval.vector import VectorHit, vector_search

__all__ = [
    "RetrievedRow",
    "VectorHit",
    "vector_search",
    "keyword_search",
    "fuse_rrf",
    "rerank",
]
