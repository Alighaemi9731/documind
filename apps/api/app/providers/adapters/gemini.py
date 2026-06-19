"""Gemini embedding adapter (ADR-0003/0014) using the ``google-genai`` SDK.

The SDK is imported lazily (only when an instance is constructed) so a default
install that never reaches a real Gemini call does not import it. Gemini does
not guarantee unit vectors, so we apply **manual L2 normalization** at ingest
and query time (``normalized=True`` pin) — this keeps cosine and inner-product
distances in agreement (ADR-0003).

Tests never construct this class against a live key; they inject a deterministic
``FakeEmbeddingProvider`` via the resolver override hook. The normalization math
is unit-tested directly through :func:`l2_normalize`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from app.providers.errors import ProviderAuthError, ProviderError, ProviderTransientError

# Task-type hints sent to the embedding endpoint.
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"

DEFAULT_MODEL = "gemini-embedding-001"
DEFAULT_DIM = 768

# Substrings that classify a raw SDK exception (status code or message).
_TRANSIENT_MARKERS = (
    "429",
    "resource_exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "503",
    "unavailable",
    "500",
    "internal",
    "deadline",
    "timeout",
    "504",
)
_AUTH_MARKERS = (
    "401",
    "403",
    "unauthenticated",
    "permission_denied",
    "permission denied",
    "api key not valid",
    "invalid api key",
    "api_key_invalid",
)


def _translate_error(exc: Exception) -> ProviderError:
    """Map a raw google-genai exception to the normalized taxonomy."""
    status = (
        getattr(exc, "code", None)
        or getattr(exc, "status_code", None)
        or getattr(exc, "status", None)
    )
    blob = f"{status} {exc}".lower()
    if any(m in blob for m in _AUTH_MARKERS):
        return ProviderAuthError(str(exc))
    if any(m in blob for m in _TRANSIENT_MARKERS):
        return ProviderTransientError(str(exc))
    return ProviderError(str(exc))


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return the L2-normalized copy of ``vector``.

    A zero (or numerically tiny) vector is returned unchanged to avoid a
    divide-by-zero; such inputs do not occur for real embeddings.
    """
    norm = math.sqrt(sum(float(x) * float(x) for x in vector))
    if norm <= 1e-12:
        return [float(x) for x in vector]
    return [float(x) / norm for x in vector]


class GeminiEmbeddingProvider:
    """``EmbeddingProvider`` backed by ``google-genai``.

    Construct from an API-key string (the decrypted operator/BYOK key). The
    SDK client is created lazily on first embed call.
    """

    def __init__(self, api_key: str, *, dim: int = DEFAULT_DIM) -> None:
        self._api_key = api_key
        self._dim = dim
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai  # lazy import (ADR-0006)

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _embed(self, texts: Sequence[str], *, model: str, task_type: str) -> list[list[float]]:
        from google.genai import types  # lazy import

        client = self._get_client()
        try:
            result = client.models.embed_content(
                model=model,
                contents=list(texts),
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._dim,
                ),
            )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize SDK errors to the taxonomy
            raise _translate_error(exc) from exc
        return [l2_normalize(e.values) for e in result.embeddings]

    def embed_documents(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts, model=model, task_type=TASK_DOCUMENT)

    def embed_query(self, text: str, *, model: str) -> list[float]:
        return self._embed([text], model=model, task_type=TASK_QUERY)[0]

    def dimension(self, model: str) -> int:
        return self._dim


__all__ = [
    "GeminiEmbeddingProvider",
    "l2_normalize",
    "DEFAULT_MODEL",
    "DEFAULT_DIM",
    "TASK_DOCUMENT",
    "TASK_QUERY",
]
