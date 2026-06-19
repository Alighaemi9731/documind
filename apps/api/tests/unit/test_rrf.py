"""RRF fusion correctness + edge cases (section 8)."""

from __future__ import annotations

import uuid

from app.rag.retrieval.fuse import RRF_K, fuse_rrf
from app.rag.retrieval.keyword import KeywordHit
from app.rag.retrieval.vector import VectorHit


def _vhit(cid: uuid.UUID, score: float) -> VectorHit:
    return VectorHit(
        chunk_id=cid,
        document_id=uuid.uuid4(),
        filename="f.txt",
        page_no=None,
        section_path=None,
        chunk_index=0,
        content="c",
        score_cosine=score,
    )


def _khit(cid: uuid.UUID, rank: float) -> KeywordHit:
    return KeywordHit(
        chunk_id=cid,
        document_id=uuid.uuid4(),
        filename="f.txt",
        page_no=None,
        section_path=None,
        chunk_index=0,
        content="c",
        rank=rank,
    )


def test_rrf_empty_legs_returns_empty() -> None:
    assert fuse_rrf([], []) == []


def test_rrf_single_leg_preserves_order() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    fused = fuse_rrf([_vhit(a, 0.9), _vhit(b, 0.8), _vhit(c, 0.7)], [])
    assert [f.row.chunk_id for f in fused] == [a, b, c]
    # Single-leg RRF score for rank r (0-based) is 1/(k+r+1).
    assert abs(fused[0].rrf_score - 1.0 / (RRF_K + 1)) < 1e-12


def test_rrf_overlap_sums_contributions() -> None:
    shared = uuid.uuid4()
    only_v = uuid.uuid4()
    only_k = uuid.uuid4()
    # ``shared`` is rank 1 in vector (0-based 0) and rank 1 in keyword (0-based 0).
    fused = fuse_rrf(
        [_vhit(shared, 0.9), _vhit(only_v, 0.1)],
        [_khit(shared, 5.0), _khit(only_k, 1.0)],
    )
    scores = {f.row.chunk_id: f.rrf_score for f in fused}
    # shared appears in both legs at the top -> 2 * 1/(k+1).
    assert abs(scores[shared] - 2.0 / (RRF_K + 1)) < 1e-12
    # shared ranks first.
    assert fused[0].row.chunk_id == shared


def test_rrf_preserves_cosine_from_vector_leg_only() -> None:
    only_v = uuid.uuid4()
    only_k = uuid.uuid4()
    fused = fuse_rrf([_vhit(only_v, 0.83)], [_khit(only_k, 1.0)])
    by_id = {f.row.chunk_id: f.row for f in fused}
    assert by_id[only_v].score_cosine == 0.83
    # A keyword-only row carries no cosine (the gate must not see a fake score).
    assert by_id[only_k].score_cosine is None


def test_rrf_tie_break_is_deterministic() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    # Both at the same single-leg rank position across two independent calls.
    f1 = fuse_rrf([_vhit(a, 0.5)], [_khit(b, 0.5)])
    f2 = fuse_rrf([_vhit(a, 0.5)], [_khit(b, 0.5)])
    assert [f.row.chunk_id for f in f1] == [f.row.chunk_id for f in f2]
