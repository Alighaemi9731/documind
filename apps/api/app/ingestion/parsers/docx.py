"""DOCX parser (python-docx) with defusedxml hardening + section offsets.

python-docx parses the OOXML with the stdlib ElementTree by default; to defend
against XXE / billion-laughs we first validate the ``word/document.xml`` member
with :func:`app.ingestion.guards.safe_parse_xml` (defusedxml) before handing the
bytes to python-docx. Each paragraph becomes a :class:`Segment` whose
``section_path`` is the most recent heading trail (``H1 > H2 > ...``). No
external relationships / OLE objects are fetched.
"""

from __future__ import annotations

import io
import zipfile

from app.ingestion.guards import GuardError, safe_parse_xml
from app.ingestion.parsers import Segment
from app.models.enums import DocumentErrorCode


def _validate_xml_members(data: bytes) -> None:
    """defusedxml-validate EVERY XML part of the docx (entity/XXE hardening).

    python-docx re-parses many parts with the stdlib parser — headers, footers,
    footnotes/endnotes, comments, styles, ``[Content_Types].xml`` and the
    ``*.rels`` relationship files — so validating only ``word/document.xml``
    would miss a billion-laughs / XXE payload planted in any other part.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.lower().endswith((".xml", ".rels")):
                safe_parse_xml(zf.read(name))


def parse_docx(data: bytes) -> list[Segment]:
    """Extract paragraph segments with a heading-trail ``section_path``."""
    _validate_xml_members(data)

    from docx import Document as DocxDocument

    try:
        document = DocxDocument(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise GuardError(DocumentErrorCode.PARSE_ERROR, "Could not read the DOCX file.") from exc

    segments: list[Segment] = []
    cursor = 0
    any_text = False
    heading_trail: list[str] = []

    for para in document.paragraphs:
        text = para.text or ""
        style_name = (para.style.name if para.style is not None else "") or ""

        if style_name.startswith("Heading") and text.strip():
            # Maintain a heading trail keyed by the heading level.
            level = _heading_level(style_name)
            heading_trail = heading_trail[: level - 1]
            heading_trail.append(text.strip())

        if text.strip():
            any_text = True

        section_path = " > ".join(heading_trail) if heading_trail else None
        start = cursor
        end = start + len(text)
        segments.append(
            Segment(text=text, char_start=start, char_end=end, section_path=section_path)
        )
        cursor = end + 1  # paragraphs joined by a newline

    if not any_text:
        raise GuardError(DocumentErrorCode.NO_TEXT, "The document contains no extractable text.")
    return segments


def _heading_level(style_name: str) -> int:
    tail = style_name.replace("Heading", "").strip()
    try:
        return max(1, int(tail))
    except ValueError:
        return 1


__all__ = ["parse_docx"]
