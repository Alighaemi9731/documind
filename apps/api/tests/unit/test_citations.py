"""Citation parsing + server-side validation against the retrieved set."""

from __future__ import annotations

import uuid

from app.rag.budget import PackedChunk, chunk_header, pack_context
from app.rag.citations import citations_from_answer, validate_citations
from app.rag.retrieval.types import RetrievedRow


def _row(filename: str, idx: int, page: int | None = None) -> RetrievedRow:
    return RetrievedRow(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename=filename,
        page_no=page,
        section_path=None,
        chunk_index=idx,
        content=f"content of {filename} chunk {idx}",
        score_cosine=0.8,
    )


def _packed(rows: list[RetrievedRow]) -> list[PackedChunk]:
    return [PackedChunk(row=r, header=chunk_header(r)) for r in rows]


def test_cited_header_resolves_to_chunk() -> None:
    r0 = _row("report.pdf", 12, page=3)
    packed = _packed([r0])
    retrieved = {r0.chunk_id}
    answer = "As shown in [report.pdf p.3 #12], the term is 5 years."
    cites = citations_from_answer(answer, packed, retrieved)
    assert len(cites) == 1
    assert cites[0]["chunk_id"] == str(r0.chunk_id)
    assert cites[0]["filename"] == "report.pdf"
    assert cites[0]["page"] == 3
    assert cites[0]["chunk_index"] == 12
    assert cites[0]["snippet"]


def test_forged_out_of_set_citation_is_dropped() -> None:
    r0 = _row("real.txt", 1)
    packed = _packed([r0])
    retrieved = {r0.chunk_id}
    # The model cites a chunk that was never retrieved (forged header).
    answer = "See [secret.txt p.9 #99] and [real.txt #1]."
    cites = citations_from_answer(answer, packed, retrieved)
    assert len(cites) == 1
    assert cites[0]["filename"] == "real.txt"


def test_validate_drops_id_not_in_retrieved_set() -> None:
    r0 = _row("a.txt", 0)
    r1 = _row("b.txt", 0)
    packed = _packed([r0, r1])
    # r1 was packed but pretend only r0 is in the authoritative retrieved set.
    cites = validate_citations([r0.chunk_id, r1.chunk_id], packed, {r0.chunk_id})
    assert [c["chunk_id"] for c in cites] == [str(r0.chunk_id)]


def test_no_citations_when_model_cites_nothing() -> None:
    r0 = _row("a.txt", 0)
    packed = _packed([r0])
    assert citations_from_answer("a plain answer", packed, {r0.chunk_id}) == []


def test_pack_context_headers_and_budget() -> None:
    rows = [_row("f.txt", i, page=i) for i in range(5)]
    packed = pack_context(rows, top_k=3, char_budget=10_000)
    assert len(packed) == 3
    assert packed[0].header == "[f.txt p.0 #0]"


def test_pack_context_includes_at_least_one_row() -> None:
    big = RetrievedRow(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="big.txt",
        page_no=None,
        section_path=None,
        chunk_index=0,
        content="x" * 50_000,
        score_cosine=0.9,
    )
    packed = pack_context([big], char_budget=100)
    assert len(packed) == 1
