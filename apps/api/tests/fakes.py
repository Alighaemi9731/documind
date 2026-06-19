"""Deterministic test doubles. NO real network calls (no GEMINI key locally).

``FakeEmbeddingProvider`` satisfies the ``EmbeddingProvider`` Protocol and emits
stable, L2-normalized vectors of a fixed dimension derived from a hash of the
text, so the same text always embeds to the same vector. Injected into the
resolver via ``set_embedding_override`` so ingestion/worker tests exercise the
real store + halfvec round-trip without any provider SDK.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence


class FakeEmbeddingProvider:
    """A deterministic, offline EmbeddingProvider for tests."""

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim
        self.embed_document_calls = 0
        self.embed_query_calls = 0

    def _vector(self, text: str) -> list[float]:
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        # Expand the 32-byte digest deterministically to ``dim`` floats in [0,1).
        raw = [seed[i % len(seed)] / 255.0 for i in range(self._dim)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed_documents(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        self.embed_document_calls += 1
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str, *, model: str) -> list[float]:
        self.embed_query_calls += 1
        return self._vector(text)

    def dimension(self, model: str) -> int:
        return self._dim


class WrongDimEmbeddingProvider(FakeEmbeddingProvider):
    """Emits vectors of the wrong dimension to exercise the store's reject path."""

    def embed_documents(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        return [[0.0] * (self._dim + 1) for _ in texts]


class RaisingEmbeddingProvider(FakeEmbeddingProvider):
    """Raises a generic error to exercise the worker's poison-job catch-all."""

    def embed_documents(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        raise RuntimeError("unexpected embedder failure")


class TransientEmbeddingProvider(FakeEmbeddingProvider):
    """Raises a normalized transient error (rate limit) — must NOT fail the doc."""

    def embed_documents(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        from app.providers.errors import ProviderTransientError

        raise ProviderTransientError("429 RESOURCE_EXHAUSTED")


__all__ = [
    "FakeEmbeddingProvider",
    "WrongDimEmbeddingProvider",
    "RaisingEmbeddingProvider",
    "TransientEmbeddingProvider",
]
