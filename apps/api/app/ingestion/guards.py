"""Upload guards (ARCHITECTURE.md section 7, security model section 14).

All extracted document text is UNTRUSTED. These guards run BEFORE parsing and
map every rejection to a typed :class:`DocumentErrorCode`:

- magic-byte sniff (``%PDF`` / ``PK\\x03\\x04`` / utf-8 text);
- extension <-> declared-mime cross-check;
- per-file size cap (``settings.max_upload_mb``);
- decompression-bomb inspection for zip-based formats (docx) — total
  uncompressed size + ~100:1 per-member ratio;
- defusedxml-hardened XML parse for docx members (billion-laughs / XXE).

:class:`GuardError` carries the error code; callers translate it to the document
status + HTTP response.
"""

from __future__ import annotations

import io
import zipfile

from app.core.config import settings
from app.models.enums import DocumentErrorCode

# Per-member uncompressed:compressed ratio above which we flag a zip bomb.
_MAX_COMPRESSION_RATIO = 100
# Absolute ceiling on total uncompressed bytes for a zip-based document.
_MAX_TOTAL_UNCOMPRESSED = 512 * 1024 * 1024

_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"

# Allowed (extension, sniffed-kind) pairs. ``kind`` is one of pdf|zip|text.
_EXT_KIND = {
    ".pdf": "pdf",
    ".docx": "zip",
    ".txt": "text",
    ".md": "text",
    ".markdown": "text",
}

# Declared MIME -> expected sniffed kind, for the cross-check.
_MIME_KIND = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "zip",
    "text/plain": "text",
    "text/markdown": "text",
    "text/x-markdown": "text",
}


class GuardError(Exception):
    """A guard rejection carrying the typed :class:`DocumentErrorCode`."""

    def __init__(self, code: DocumentErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _ext(filename: str) -> str:
    name = filename.lower()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def sniff_kind(head: bytes) -> str | None:
    """Best-effort content-kind from leading magic bytes.

    Returns ``"pdf"`` / ``"zip"`` / ``"text"`` or ``None`` if it does not look
    like any accepted type.
    """
    if head.startswith(_PDF_MAGIC):
        return "pdf"
    if head.startswith(_ZIP_MAGIC):
        return "zip"
    # utf-8 decodable head with no NUL bytes => treat as text.
    if b"\x00" in head:
        return None
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        # A multibyte char may be split at the boundary; retry ignoring tail.
        try:
            head[: max(0, len(head) - 4)].decode("utf-8")
        except UnicodeDecodeError:
            return None
    return "text"


def check_size(size_bytes: int) -> None:
    """Raise ``OVERSIZE`` if the file exceeds the configured cap."""
    cap = settings.max_upload_mb * 1024 * 1024
    if size_bytes > cap:
        raise GuardError(
            DocumentErrorCode.OVERSIZE,
            f"File exceeds the {settings.max_upload_mb} MB upload limit.",
        )


def check_type(filename: str, declared_mime: str, head: bytes) -> str:
    """Cross-check extension, declared MIME, and magic bytes. Return the kind.

    Raises ``BAD_TYPE`` if the extension is unsupported or any of the three
    signals disagree.
    """
    ext = _ext(filename)
    if ext not in _EXT_KIND:
        raise GuardError(DocumentErrorCode.BAD_TYPE, f"Unsupported file extension: {ext or '?'}.")
    ext_kind = _EXT_KIND[ext]

    sniffed = sniff_kind(head)
    if sniffed is None or sniffed != ext_kind:
        raise GuardError(
            DocumentErrorCode.BAD_TYPE,
            "File content does not match its extension.",
        )

    if declared_mime:
        mime_kind = _MIME_KIND.get(declared_mime.split(";")[0].strip().lower())
        # An unknown/blank MIME is tolerated; a *contradicting* one is rejected.
        if mime_kind is not None and mime_kind != ext_kind:
            raise GuardError(
                DocumentErrorCode.BAD_TYPE,
                "Declared content-type does not match the file extension.",
            )
    return ext_kind


def check_zip_bomb(data: bytes) -> None:
    """Inspect a zip-based document for decompression-bomb characteristics.

    Raises ``DECOMPRESSION_BOMB`` on an excessive total uncompressed size or a
    per-member compression ratio above ``_MAX_COMPRESSION_RATIO``.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            total = 0
            for info in zf.infolist():
                total += info.file_size
                if total > _MAX_TOTAL_UNCOMPRESSED:
                    raise GuardError(
                        DocumentErrorCode.DECOMPRESSION_BOMB,
                        "Archive uncompressed size exceeds the safety ceiling.",
                    )
                if info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > _MAX_COMPRESSION_RATIO:
                        raise GuardError(
                            DocumentErrorCode.DECOMPRESSION_BOMB,
                            "Archive member compression ratio is suspiciously high.",
                        )
    except zipfile.BadZipFile as exc:
        raise GuardError(DocumentErrorCode.BAD_TYPE, "Corrupt or invalid archive.") from exc


def safe_parse_xml(xml_bytes: bytes):  # noqa: ANN201 - defusedxml Element
    """Parse XML with defusedxml (XXE / billion-laughs hardened).

    Raises ``DECOMPRESSION_BOMB`` on an entity-expansion (billion-laughs) bomb
    and ``PARSE_ERROR`` on other malformed XML.
    """
    from defusedxml.common import EntitiesForbidden, ExternalReferenceForbidden
    from defusedxml.ElementTree import fromstring

    try:
        return fromstring(xml_bytes)
    except (EntitiesForbidden, ExternalReferenceForbidden) as exc:
        raise GuardError(
            DocumentErrorCode.DECOMPRESSION_BOMB,
            "XML entity expansion / external reference rejected.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise GuardError(DocumentErrorCode.PARSE_ERROR, "Malformed XML document.") from exc


def run_guards(filename: str, declared_mime: str, data: bytes) -> str:
    """Run all guards on a fully-buffered file. Return the detected kind.

    Size is assumed already enforced mid-stream by the upload route; we re-check
    here defensively.
    """
    check_size(len(data))
    kind = check_type(filename, declared_mime, data[:512])
    if kind == "zip":
        check_zip_bomb(data)
    return kind


__all__ = [
    "GuardError",
    "sniff_kind",
    "check_size",
    "check_type",
    "check_zip_bomb",
    "safe_parse_xml",
    "run_guards",
]
