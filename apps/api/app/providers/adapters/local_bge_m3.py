"""Local BAAI/bge-m3 embedding adapter (EMBEDDING-ONLY, opt-in, worker process).

OFF by default. Loading is gated behind ``settings.enable_local_embeddings`` AND
a documented >=4GB RAM floor; the worker pins torch to 1-2 threads. The
``sentence-transformers`` model is a lazy singleton (loaded once on first embed)
so a default install never imports torch / sentence-transformers (ADR-0006) and
the heavy weights load only in the ingestion-worker process, never the web tier
(ARCHITECTURE.md section 9). ``sentence-transformers`` + ``torch`` are an OPTIONAL
extra (``local-embeddings`` group); refusing to load on a too-small box keeps the
2GB default profile safe.

Dim 1024, normalized.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.core.config import settings

MODEL_NAME = "BAAI/bge-m3"
DEFAULT_DIM = 1024
# Documented minimum RAM (bytes) below which loading is refused without override.
MIN_RAM_BYTES = 4 * 1024 * 1024 * 1024
# torch thread cap (ARCHITECTURE.md section 9: pin to 1-2 threads).
TORCH_THREADS = 1

# Process-level lazy singleton (the model is large; load once).
_model: Any | None = None


class LocalEmbeddingsDisabled(RuntimeError):
    """Raised when local embeddings are not enabled or the host is too small."""


def _available_ram_bytes() -> int | None:
    """Best-effort total RAM in bytes, or None if it can't be determined."""
    try:
        import os

        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page_size)
    except (ValueError, OSError, AttributeError):
        return None


def _ensure_enabled(*, allow_small_ram: bool = False) -> None:
    if not settings.enable_local_embeddings:
        raise LocalEmbeddingsDisabled(
            "Local bge-m3 embeddings are disabled (set ENABLE_LOCAL_EMBEDDINGS)."
        )
    if not allow_small_ram:
        ram = _available_ram_bytes()
        if ram is not None and ram < MIN_RAM_BYTES:
            raise LocalEmbeddingsDisabled(
                "Local bge-m3 requires >=4GB RAM; refusing to load on this host."
            )


def _get_model(*, allow_small_ram: bool = False) -> Any:
    """Lazily load the sentence-transformers model singleton (worker only)."""
    global _model
    if _model is None:
        _ensure_enabled(allow_small_ram=allow_small_ram)
        try:
            import torch  # lazy import (optional extra)

            torch.set_num_threads(TORCH_THREADS)
        except Exception:  # noqa: BLE001 - torch optional / threadcap best-effort
            pass
        from sentence_transformers import SentenceTransformer  # lazy import

        _model = SentenceTransformer(MODEL_NAME)
    return _model


class LocalBgeM3EmbeddingProvider:
    """``EmbeddingProvider`` backed by sentence-transformers bge-m3 (embedding-only).

    The constructor does NOT load the model — the singleton is materialized on
    the first embed call so importing this module stays cheap.
    """

    def __init__(self, api_key: str = "", *, dim: int = DEFAULT_DIM) -> None:
        # api_key is unused (local model) but kept for a uniform adapter ctor.
        self._dim = dim

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        model = _get_model()
        vectors = model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [list(map(float, v)) for v in vectors]

    def embed_documents(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts)

    def embed_query(self, text: str, *, model: str) -> list[float]:
        return self._embed([text])[0]

    def dimension(self, model: str) -> int:
        return self._dim


__all__ = [
    "LocalBgeM3EmbeddingProvider",
    "LocalEmbeddingsDisabled",
    "MODEL_NAME",
    "DEFAULT_DIM",
    "MIN_RAM_BYTES",
]
