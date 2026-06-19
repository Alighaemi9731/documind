"""Shared retrieval row type (a single retrieved chunk + its locators).

A ``RetrievedRow`` carries everything the prompt builder, citation validator, and
Citation contract need, without re-querying: the chunk id + tenant-safe locators
(document_id, filename, page, section_path, chunk_index) and the chunk content.

The ``score_cosine`` field holds the **raw cosine similarity** (``1 - distance``)
of the vector leg, present only on rows the vector leg returned; it is the SOLE
trust anchor for grounding (ADR-0008). It is deliberately separate from any RRF
fusion score so the grounding gate can never key off a fused ordering score.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedRow:
    """One retrieved chunk with citation locators and (optional) raw cosine."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_no: int | None
    section_path: str | None
    chunk_index: int
    content: str
    # Raw cosine SIMILARITY (1 - cosine_distance) from the vector leg, or None
    # if this row came only from the keyword leg. NEVER an RRF score.
    score_cosine: float | None = None


__all__ = ["RetrievedRow"]
