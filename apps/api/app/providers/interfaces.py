"""The two narrow provider Protocols (ARCHITECTURE.md section 9, ADR-0006).

Adapters implement only the surface the app actually needs. Structural typing
(``Protocol``) means a deterministic fake in tests satisfies the interface
without inheritance — used to inject a ``FakeEmbeddingProvider`` so no real
network call happens in Phase-2 tests.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ChatDelta:
    """One streamed chunk of an LLM response."""

    text: str


@dataclass(frozen=True)
class ChatResult:
    """A complete (non-streamed) LLM response."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class LLMProvider(Protocol):
    """Chat capability. Unused in Phase 2 (embedding only) but defined now."""

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        system: str,
        max_tokens: int,
    ) -> ChatResult: ...

    def chat_stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        system: str,
        max_tokens: int,
    ) -> Iterator[ChatDelta]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Embedding capability — the Phase-2 path.

    ``embed_documents`` embeds ingest chunks (``RETRIEVAL_DOCUMENT`` task);
    ``embed_query`` embeds a search query (``RETRIEVAL_QUERY`` task). Both
    return L2-normalized vectors when the model's pin declares ``normalized``.
    """

    def embed_documents(self, texts: Sequence[str], *, model: str) -> list[list[float]]: ...

    def embed_query(self, text: str, *, model: str) -> list[float]: ...

    def dimension(self, model: str) -> int: ...


__all__ = [
    "ChatDelta",
    "ChatResult",
    "LLMProvider",
    "EmbeddingProvider",
]
