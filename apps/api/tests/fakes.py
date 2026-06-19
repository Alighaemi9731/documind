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
from collections.abc import Iterator, Sequence

from app.providers.interfaces import ChatDelta, ChatResult


class FakeChatProvider:
    """A deterministic, offline streaming chat provider for tests.

    Streams a scripted answer split into small pieces (so the sentinel-stripping
    filter is exercised across arbitrary token boundaries) and appends the
    grounding sentinel. ``chunk_size`` controls how finely the script is split.
    ``called`` records whether the provider was invoked (so a refusal test can
    assert NO chat call happened).
    """

    def __init__(
        self,
        answer: str,
        *,
        grounded: bool = True,
        chunk_size: int = 3,
        sentinel: str | None = None,
    ) -> None:
        self._answer = answer
        if sentinel is not None:
            self._sentinel = sentinel
        else:
            self._sentinel = "<<<GROUNDED:true>>>" if grounded else "<<<GROUNDED:false>>>"
        self._chunk_size = max(1, chunk_size)
        self.called = False
        self.call_count = 0

    @property
    def _script(self) -> str:
        return f"{self._answer}\n{self._sentinel}"

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        system: str,
        max_tokens: int,
    ) -> ChatResult:
        self.called = True
        self.call_count += 1
        return ChatResult(text=self._script, input_tokens=0, output_tokens=0)

    def chat_stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        system: str,
        max_tokens: int,
    ) -> Iterator[ChatDelta]:
        self.called = True
        self.call_count += 1
        text = self._script
        for i in range(0, len(text), self._chunk_size):
            yield ChatDelta(text=text[i : i + self._chunk_size])


class RaisingChatProvider:
    """A chat provider whose stream raises mid-flight (exercises the SSE error
    frame). The error message must NOT leak into the client stream."""

    def __init__(self) -> None:
        self.called = False

    def chat(
        self, messages: Sequence[dict[str, str]], *, model: str, system: str, max_tokens: int
    ) -> ChatResult:
        from app.providers.errors import ProviderTransientError

        self.called = True
        raise ProviderTransientError("429 RESOURCE_EXHAUSTED boom")

    def chat_stream(
        self, messages: Sequence[dict[str, str]], *, model: str, system: str, max_tokens: int
    ) -> Iterator[ChatDelta]:
        from app.providers.errors import ProviderTransientError

        self.called = True
        raise ProviderTransientError("429 RESOURCE_EXHAUSTED boom")
        yield ChatDelta(text="")  # noqa: unreachable - makes this a generator


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
    "FakeChatProvider",
    "RaisingChatProvider",
    "FakeEmbeddingProvider",
    "WrongDimEmbeddingProvider",
    "RaisingEmbeddingProvider",
    "TransientEmbeddingProvider",
]
