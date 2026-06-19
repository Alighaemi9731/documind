"""Normalized provider error taxonomy (ADR-0006).

Adapters translate provider-SDK exceptions into these so the ingest worker and
the RAG layer can react uniformly: a ``ProviderTransientError`` is retried
(rate limit / quota / 5xx / timeout) and never fails the document; an auth or
invalid-key error is terminal.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base for a normalized provider failure."""


class ProviderTransientError(ProviderError):
    """Retryable failure — rate limit, quota, 5xx, or timeout. Do not fail."""


class ProviderAuthError(ProviderError):
    """Authentication / permission failure (bad or revoked key)."""


class ProviderInvalidKeyError(ProviderError):
    """The supplied key is malformed or rejected as invalid."""


__all__ = [
    "ProviderError",
    "ProviderTransientError",
    "ProviderAuthError",
    "ProviderInvalidKeyError",
]
