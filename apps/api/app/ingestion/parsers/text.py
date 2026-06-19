"""Plain-text / Markdown parser. Decodes the bytes as a single segment.

Decoding tries utf-8, then utf-8-sig (BOM), then latin-1 as a last resort so a
mis-encoded file still yields *some* text rather than failing. The whole file is
one :class:`Segment` (offsets 0..len); the chunker performs the actual splitting.
"""

from __future__ import annotations

from app.ingestion.guards import GuardError
from app.ingestion.parsers import Segment
from app.models.enums import DocumentErrorCode


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def parse_text(data: bytes) -> list[Segment]:
    """Decode a plain-text / markdown file into a single text segment."""
    text = _decode(data)
    if not text.strip():
        raise GuardError(DocumentErrorCode.NO_TEXT, "The file contains no text.")
    return [Segment(text=text, char_start=0, char_end=len(text))]


__all__ = ["parse_text"]
