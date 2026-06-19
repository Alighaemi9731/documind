"""On-disk storage for uploaded files (NOT in Postgres, ARCHITECTURE.md section 2).

Files are written under ``settings.uploads_dir`` keyed by document id. The
worker reads the bytes back by id. A streaming writer enforces the size cap
mid-stream so a hostile upload never buffers the whole file in RAM.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from app.core.config import settings
from app.ingestion.guards import GuardError
from app.models.enums import DocumentErrorCode


def _uploads_root() -> Path:
    root = Path(settings.uploads_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def document_path(document_id: uuid.UUID) -> Path:
    """Filesystem path that holds the raw bytes for ``document_id``."""
    return _uploads_root() / f"{document_id}.bin"


async def write_stream(
    chunks: AsyncIterator[bytes], *, dest: Path, max_bytes: int
) -> tuple[int, bytes]:
    """Stream ``chunks`` to ``dest``, enforcing ``max_bytes`` mid-stream.

    Returns ``(size, head)`` where ``head`` is the first up-to-512 bytes (for
    magic-byte sniffing) without re-reading the file. Raises ``OVERSIZE`` as
    soon as the cap is crossed.
    """
    size = 0
    head = b""
    with dest.open("wb") as fh:
        async for chunk in chunks:
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes:
                fh.close()
                dest.unlink(missing_ok=True)
                raise GuardError(DocumentErrorCode.OVERSIZE, "Upload exceeds the size limit.")
            if len(head) < 512:
                head += chunk[: 512 - len(head)]
            fh.write(chunk)
    return size, head


async def read_document_bytes(document_id: uuid.UUID) -> bytes:
    """Read the stored bytes for ``document_id`` (worker entry point)."""
    return document_path(document_id).read_bytes()


def delete_document_file(document_id: uuid.UUID) -> None:
    """Remove the stored file for ``document_id`` (best effort)."""
    document_path(document_id).unlink(missing_ok=True)


__all__ = [
    "document_path",
    "write_stream",
    "read_document_bytes",
    "delete_document_file",
]
