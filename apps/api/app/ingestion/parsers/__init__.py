"""Document parsers. Each yields :class:`Segment` with precise char offsets.

A ``Segment`` carries the extracted text plus the locator used for citations:
``page_no`` (PDF) and/or ``section_path`` (DOCX), and the ``char_start`` /
``char_end`` offsets into the document's concatenated text. All parsing runs
with NO network egress (no external entity / URL / relationship fetch).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """A located run of extracted text within a document."""

    text: str
    char_start: int
    char_end: int
    page_no: int | None = None
    section_path: str | None = None


__all__ = ["Segment"]
