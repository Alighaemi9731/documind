"""Upload-guard unit tests — one per DocumentErrorCode incl. billion-laughs."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.ingestion.guards import (
    GuardError,
    check_size,
    check_type,
    check_zip_bomb,
    run_guards,
    sniff_kind,
)
from app.models.enums import DocumentErrorCode

PDF_BYTES = b"%PDF-1.4\n%fake pdf body\n"
TEXT_BYTES = "hello world\nسلام دنیا\n".encode()


def _zip(members: dict[str, bytes], *, compresslevel: int | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_sniff_kind() -> None:
    assert sniff_kind(PDF_BYTES) == "pdf"
    assert sniff_kind(b"PK\x03\x04rest") == "zip"
    assert sniff_kind(TEXT_BYTES) == "text"
    assert sniff_kind(b"\x00\x01\x02binary") is None


def test_oversize() -> None:
    with pytest.raises(GuardError) as exc:
        check_size(10**12)
    assert exc.value.code is DocumentErrorCode.OVERSIZE


def test_bad_type_unknown_extension() -> None:
    with pytest.raises(GuardError) as exc:
        check_type("evil.exe", "application/octet-stream", b"MZ\x90\x00")
    assert exc.value.code is DocumentErrorCode.BAD_TYPE


def test_bad_type_extension_content_mismatch() -> None:
    # .pdf extension but text content => BAD_TYPE.
    with pytest.raises(GuardError) as exc:
        check_type("notes.pdf", "application/pdf", TEXT_BYTES)
    assert exc.value.code is DocumentErrorCode.BAD_TYPE


def test_bad_type_contradicting_mime() -> None:
    with pytest.raises(GuardError) as exc:
        check_type("doc.pdf", "text/plain", PDF_BYTES)
    assert exc.value.code is DocumentErrorCode.BAD_TYPE


def test_type_ok_for_pdf_and_text() -> None:
    assert check_type("a.pdf", "application/pdf", PDF_BYTES) == "pdf"
    assert check_type("a.md", "text/markdown", TEXT_BYTES) == "text"


def test_decompression_bomb_ratio() -> None:
    # One highly-compressible member => high uncompressed:compressed ratio.
    bomb = _zip({"word/document.xml": b"A" * (5 * 1024 * 1024)})
    with pytest.raises(GuardError) as exc:
        check_zip_bomb(bomb)
    assert exc.value.code is DocumentErrorCode.DECOMPRESSION_BOMB


def test_zip_bomb_corrupt_archive_is_bad_type() -> None:
    with pytest.raises(GuardError) as exc:
        check_zip_bomb(b"PK\x03\x04not-a-real-zip")
    assert exc.value.code is DocumentErrorCode.BAD_TYPE


def test_billion_laughs_xml_rejected() -> None:
    """Entity-expansion (billion-laughs) XML must be rejected by defusedxml."""
    pytest.importorskip("defusedxml")
    from app.ingestion.guards import safe_parse_xml

    billion_laughs = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
      <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
    ]>
    <lolz>&lol3;</lolz>"""
    with pytest.raises(GuardError) as exc:
        safe_parse_xml(billion_laughs)
    assert exc.value.code is DocumentErrorCode.DECOMPRESSION_BOMB


def test_run_guards_happy_path_text() -> None:
    assert run_guards("readme.md", "text/markdown", TEXT_BYTES) == "text"
