"""Reranker: exact-phrase boost + bounded filename bonus can't dominate."""

from __future__ import annotations

import uuid

from app.rag.retrieval.fuse import FusedRow
from app.rag.retrieval.rerank import rerank
from app.rag.retrieval.types import RetrievedRow


def _fused(filename: str, content: str, rrf: float) -> FusedRow:
    row = RetrievedRow(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename=filename,
        page_no=None,
        section_path=None,
        chunk_index=0,
        content=content,
        score_cosine=0.5,
    )
    return FusedRow(row=row, rrf_score=rrf)


def test_exact_phrase_match_boosts_rank() -> None:
    a = _fused("a.txt", "nothing relevant here", rrf=0.02)
    b = _fused("b.txt", "the special phrase appears here", rrf=0.01)
    ordered = rerank([a, b], query="special phrase")
    # b has the exact phrase => it should outrank a despite lower RRF.
    assert ordered[0].filename == "b.txt"


def test_filename_bonus_is_bounded_and_cannot_dominate() -> None:
    # An attacker-named file stuffed with query terms in the FILENAME only.
    attacker = _fused(
        "special phrase special phrase special phrase.txt",
        "irrelevant body text",
        rrf=0.001,
    )
    # A genuinely strong content match with much higher RRF.
    genuine = _fused("doc.txt", "the special phrase is in the body", rrf=0.05)
    ordered = rerank([attacker, genuine], query="special phrase")
    assert ordered[0].filename == "doc.txt"


def test_rerank_is_deterministic() -> None:
    a = _fused("a.txt", "body", rrf=0.02)
    b = _fused("b.txt", "body", rrf=0.02)
    o1 = rerank([a, b], query="q")
    o2 = rerank([a, b], query="q")
    assert [r.chunk_id for r in o1] == [r.chunk_id for r in o2]
