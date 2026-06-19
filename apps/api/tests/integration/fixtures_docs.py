"""Tiny generated document fixtures for parser/ingestion integration tests.

``make_text_pdf`` hand-builds a minimal, valid single-/multi-page PDF whose
pages contain the given text via a Tj content stream, so pypdf extracts it
without a heavy generator dependency (reportlab is not a project dependency).
"""

from __future__ import annotations


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_text_pdf(pages: list[str]) -> bytes:
    """Build a minimal PDF with one text line per page (ASCII content)."""
    objects: list[bytes] = []

    # 1: Catalog, 2: Pages, then per page: Page + Contents, plus a shared font.
    font_obj_num = 3 + 2 * len(pages)
    page_obj_nums = [3 + 2 * i for i in range(len(pages))]
    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())

    for i, text in enumerate(pages):
        content_num = page_obj_nums[i] + 1
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
            f"/Contents {content_num} 0 R >>"
        ).encode()
        objects.append(page)
        stream = f"BT /F1 24 Tf 72 720 Td ({_escape(text)}) Tj ET".encode()
        content = (
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
        objects.append(content)

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # Assemble with a cross-reference table.
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{idx} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_pos = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    return bytes(out)


PERSIAN_TEXT = "این یک سند فارسی برای آزمایش است.\nبخش دوم: پردازش متن چندزبانه.\nمی‌رود و می‌آید.\n"


__all__ = ["make_text_pdf", "PERSIAN_TEXT"]
