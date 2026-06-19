"""Citation construction + server-side validation (ADR-0008, section 6).

The canonical Citation (section 6) is::

    {chunk_id, document_id, filename, page, section_path, chunk_index, score, snippet}

Every citation the model emits is validated against the EXACT retrieved
``chunk_id`` set for THIS request; any id not in the set is dropped (a forged or
hallucinated reference cannot survive). The model cites by the bracketed header
``[filename p.X #idx]``; we extract the referenced ``(filename, chunk_index)``
pairs and resolve them back to the retrieved rows. We additionally accept a raw
chunk_id appearing in the text (defensive), but only if it is in the retrieved
set.

Building the Citation list is done from the retrieved rows (the trusted source),
never from model-asserted fields, so filename/page/etc. can't be spoofed.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from typing import Any

from app.rag.budget import PackedChunk
from app.rag.retrieval.types import RetrievedRow

# Snippet length for the Citation.snippet preview.
_SNIPPET_CHARS = 240

# Header references like "[report.pdf p.3 #12]" or "[notes.txt #4]".
_HEADER_REF_RE = re.compile(r"\[(?P<file>[^\]\n]+?)\s*(?:p\.\d+\s*)?#(?P<idx>\d+)\]")
# A bare UUID mentioned in the text (defensive secondary path).
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def _snippet(content: str) -> str:
    text = " ".join(content.split())
    return text[:_SNIPPET_CHARS]


def build_citation(row: RetrievedRow) -> dict[str, Any]:
    """Build the canonical Citation dict from a retrieved row (trusted source)."""
    return {
        "chunk_id": str(row.chunk_id),
        "document_id": str(row.document_id),
        "filename": row.filename,
        "page": row.page_no,
        "section_path": row.section_path,
        "chunk_index": row.chunk_index,
        "score": row.score_cosine,
        "snippet": _snippet(row.content),
    }


def cited_chunk_ids(
    answer_text: str,
    packed: Sequence[PackedChunk],
) -> list[uuid.UUID]:
    """Resolve the chunk_ids the model referenced, restricted to the packed set.

    Matches bracketed ``[filename ... #idx]`` headers (and any bare chunk_id) in
    ``answer_text`` against the packed rows by ``(filename, chunk_index)``.
    Returns retrieved chunk_ids only (dedup, order of first appearance).
    """
    by_file_idx: dict[tuple[str, int], uuid.UUID] = {}
    by_uuid: dict[str, uuid.UUID] = {}
    for item in packed:
        row = item.row
        by_file_idx[(row.filename, row.chunk_index)] = row.chunk_id
        by_uuid[str(row.chunk_id)] = row.chunk_id

    found: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    for match in _HEADER_REF_RE.finditer(answer_text or ""):
        filename = match.group("file").strip()
        idx = int(match.group("idx"))
        cid = by_file_idx.get((filename, idx))
        if cid is not None and cid not in seen:
            seen.add(cid)
            found.append(cid)

    for match in _UUID_RE.finditer(answer_text or ""):
        cid = by_uuid.get(match.group(0))
        if cid is not None and cid not in seen:
            seen.add(cid)
            found.append(cid)

    return found


def validate_citations(
    cited_ids: Sequence[uuid.UUID],
    packed: Sequence[PackedChunk],
    retrieved_ids: set[uuid.UUID],
) -> list[dict[str, Any]]:
    """Return canonical Citations for cited ids that ARE in the retrieved set.

    Any cited id not present in ``retrieved_ids`` is dropped (forged/hallucinated
    reference). Citations are built from the packed rows (trusted locators).
    """
    rows_by_id = {item.row.chunk_id: item.row for item in packed}
    citations: list[dict[str, Any]] = []
    for cid in cited_ids:
        if cid not in retrieved_ids:
            continue
        row = rows_by_id.get(cid)
        if row is None:
            continue
        citations.append(build_citation(row))
    return citations


def citations_from_answer(
    answer_text: str,
    packed: Sequence[PackedChunk],
    retrieved_ids: set[uuid.UUID],
) -> list[dict[str, Any]]:
    """Parse + validate in one step: model text -> validated Citation[]."""
    return validate_citations(
        cited_chunk_ids(answer_text, packed), packed, retrieved_ids
    )


__all__ = [
    "build_citation",
    "cited_chunk_ids",
    "validate_citations",
    "citations_from_answer",
]
