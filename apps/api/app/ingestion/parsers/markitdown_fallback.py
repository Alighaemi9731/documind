"""markitdown fallback — used ONLY when a primary parser yields no usable text.

The primary parsers (pypdf / python-docx) give precise page/section offsets, so
markitdown is a last resort for files they could not extract. It returns a
single :class:`Segment` (no page/section locators). The library is imported
lazily so a default install does not pay its import cost unless it is needed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.ingestion.guards import GuardError
from app.ingestion.parsers import Segment
from app.models.enums import DocumentErrorCode


def parse_with_markitdown(data: bytes, *, suffix: str) -> list[Segment]:
    """Best-effort extraction via markitdown. Raises ``NO_TEXT`` if still empty."""
    try:
        from markitdown import MarkItDown
    except Exception as exc:  # noqa: BLE001 - optional/heavy dependency
        raise GuardError(
            DocumentErrorCode.NO_TEXT, "No extractable text (fallback unavailable)."
        ) from exc

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(data)
        try:
            result = MarkItDown().convert(str(path))
        except Exception as exc:  # noqa: BLE001
            raise GuardError(
                DocumentErrorCode.NO_TEXT, "No extractable text (fallback failed)."
            ) from exc

    text = (result.text_content or "").strip()
    if not text:
        raise GuardError(DocumentErrorCode.NO_TEXT, "No extractable text.")
    return [Segment(text=text, char_start=0, char_end=len(text))]


__all__ = ["parse_with_markitdown"]
