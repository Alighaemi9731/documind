"""PDF parser (pypdf), per-page char offsets for citations.

- Encrypted PDFs that cannot be opened with an empty password -> ``ENCRYPTED_PDF``.
- Image-only / no-extractable-text PDFs -> ``NO_TEXT`` (NO OCR in v1).
- Any other failure -> ``PARSE_ERROR``.

No network egress: pypdf does not fetch remote resources; we never execute PDF
actions/JS. Each page becomes one :class:`Segment` carrying ``page_no`` (1-based)
and the char span into the concatenated document text (pages joined by ``\\n``).
"""

from __future__ import annotations

import io

from app.ingestion.guards import GuardError
from app.ingestion.parsers import Segment
from app.models.enums import DocumentErrorCode

# Defensive ceiling on pages (ARCHITECTURE.md section 7).
MAX_PAGES = 2000


def parse_pdf(data: bytes) -> list[Segment]:
    """Extract per-page segments from a PDF byte string."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise GuardError(DocumentErrorCode.PARSE_ERROR, "Could not read the PDF.") from exc

    if reader.is_encrypted:
        # Try an empty-password decrypt; if it fails, the PDF is truly encrypted.
        try:
            if reader.decrypt("") == 0:  # 0 == failed
                raise GuardError(DocumentErrorCode.ENCRYPTED_PDF, "The PDF is password-protected.")
        except GuardError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GuardError(
                DocumentErrorCode.ENCRYPTED_PDF, "The PDF is password-protected."
            ) from exc

    pages = reader.pages
    if len(pages) > MAX_PAGES:
        raise GuardError(
            DocumentErrorCode.TOO_MANY_CHUNKS,
            f"PDF has more than {MAX_PAGES} pages.",
        )

    segments: list[Segment] = []
    cursor = 0
    any_text = False
    for idx, page in enumerate(pages):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - a bad page should not abort the whole doc
            text = ""
        if text.strip():
            any_text = True
        start = cursor
        end = start + len(text)
        segments.append(Segment(text=text, char_start=start, char_end=end, page_no=idx + 1))
        # Pages are joined by a newline in the concatenated document text.
        cursor = end + 1

    if not any_text:
        raise GuardError(
            DocumentErrorCode.NO_TEXT,
            "No extractable text (image-only or scanned PDF; OCR is not supported).",
        )
    return segments


__all__ = ["parse_pdf", "MAX_PAGES"]
