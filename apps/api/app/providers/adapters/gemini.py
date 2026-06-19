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
from collections.abc import Iterator, Sequence
from typing import Any

from app.providers.errors import ProviderAuthError, ProviderError, ProviderTransientError
from app.providers.interfaces import ChatDelta, ChatResult

# Task-type hints sent to the embedding endpoint.
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"

DEFAULT_MODEL = "gemini-embedding-001"
DEFAULT_DIM = 768
# Operator-default Gemini chat model (ADR-0006; Gemini is the shared default).
DEFAULT_CHAT_MODEL = "gemini-2.0-flash"

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


class GeminiChatProvider:
    """``LLMProvider`` backed by ``google-genai`` (chat + streaming chat).

    Construct from an API-key string (the decrypted operator/BYOK key). The SDK
    client is created lazily on first call so a default install does not import
    ``google-genai`` until a real chat happens (ADR-0006). SDK exceptions are
    normalized into the :mod:`app.providers.errors` taxonomy. The system prompt
    is passed via ``system_instruction``; chat messages map to SDK ``contents``.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai  # lazy import (ADR-0006)

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    @staticmethod
    def _to_contents(messages: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
        """Map ``[{role, content}]`` to google-genai ``contents`` structures.

        The assistant role is ``model`` in the Gemini schema; everything else is
        ``user``.
        """
        contents: list[dict[str, Any]] = []
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        return contents

    def _config(self, *, system: str, max_tokens: int) -> Any:
        from google.genai import types  # lazy import

        return types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        )

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        system: str,
        max_tokens: int,
    ) -> ChatResult:
        client = self._get_client()
        try:
            response = client.models.generate_content(
                model=model,
                contents=self._to_contents(messages),
                config=self._config(system=system, max_tokens=max_tokens),
            )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize SDK errors
            raise _translate_error(exc) from exc
        text = getattr(response, "text", "") or ""
        usage = getattr(response, "usage_metadata", None)
        return ChatResult(
            text=text,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
        )

    def chat_stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        system: str,
        max_tokens: int,
    ) -> Iterator[ChatDelta]:
        client = self._get_client()
        try:
            stream = client.models.generate_content_stream(
                model=model,
                contents=self._to_contents(messages),
                config=self._config(system=system, max_tokens=max_tokens),
            )
            for event in stream:
                text = getattr(event, "text", None)
                if text:
                    yield ChatDelta(text=text)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize SDK errors
            raise _translate_error(exc) from exc


__all__ = [
    "GeminiEmbeddingProvider",
    "GeminiChatProvider",
    "l2_normalize",
    "DEFAULT_MODEL",
    "DEFAULT_DIM",
    "DEFAULT_CHAT_MODEL",
    "TASK_DOCUMENT",
    "TASK_QUERY",
]
