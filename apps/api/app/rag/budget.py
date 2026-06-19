"""Context budgeting (section 8) — pack top-K chunks under a char-based budget.

Selects up to ``CONTEXT_TOPK`` reranked rows and renders each with a
``[filename p.X #idx]`` header so the model can cite by the provided id/locator.
A char-based token heuristic (no bundled tokenizer) caps the total context size;
once the budget is exhausted, remaining rows are dropped. The chunk content is
NOT neutralized here — neutralization + nonce fencing happen in
:mod:`app.rag.prompt` at fence-assembly time, on exactly the rows this module
selects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.rag.retrieval.types import RetrievedRow

# How many chunks to consider packing (section 8).
CONTEXT_TOPK = 8
# Char budget for the packed context (~ chars/4 token heuristic; ~3k tokens).
CONTEXT_CHAR_BUDGET = 12_000


@dataclass(frozen=True)
class PackedChunk:
    """A selected chunk with its citation header line."""

    row: RetrievedRow
    header: str


def chunk_header(row: RetrievedRow) -> str:
    """Render the ``[filename p.X #idx]`` citation header for a row."""
    page = f" p.{row.page_no}" if row.page_no is not None else ""
    return f"[{row.filename}{page} #{row.chunk_index}]"


def pack_context(
    rows: Sequence[RetrievedRow],
    *,
    top_k: int = CONTEXT_TOPK,
    char_budget: int = CONTEXT_CHAR_BUDGET,
) -> list[PackedChunk]:
    """Select up to ``top_k`` rows that fit under ``char_budget`` (header+body).

    Always includes at least the first row even if it alone exceeds the budget
    (so a single long chunk is still answerable); subsequent rows are added
    while they fit.
    """
    packed: list[PackedChunk] = []
    used = 0
    for row in rows[:top_k]:
        header = chunk_header(row)
        cost = len(header) + len(row.content) + 2
        if packed and used + cost > char_budget:
            break
        packed.append(PackedChunk(row=row, header=header))
        used += cost
    return packed


__all__ = ["CONTEXT_TOPK", "CONTEXT_CHAR_BUDGET", "PackedChunk", "chunk_header", "pack_context"]
