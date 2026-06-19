"""Groq chat adapter using the official ``groq`` SDK (chat-only).

Lazily imports the SDK (ADR-0006). Default model
``llama-3.3-70b-versatile``. Groq has no embeddings, so the embedding capability
is unsupported in the registry. SDK exceptions are normalized into
:mod:`app.providers.errors`. Tests inject a stubbed ``groq`` module.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from app.providers.errors import (
    ProviderError,
    ProviderInvalidKeyError,
    ProviderTransientError,
)
from app.providers.interfaces import ChatDelta, ChatResult

DEFAULT_CHAT_MODEL = "llama-3.3-70b-versatile"

_TRANSIENT_MARKERS = (
    "429",
    "rate limit",
    "rate_limit",
    "overloaded",
    "500",
    "502",
    "503",
    "504",
    "timeout",
    "timed out",
    "service unavailable",
)
_AUTH_MARKERS = (
    "401",
    "403",
    "invalid api key",
    "invalid_api_key",
    "authentication",
    "permission",
)


def _translate_error(exc: Exception) -> ProviderError:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    blob = f"{status} {exc}".lower()
    if any(m in blob for m in _AUTH_MARKERS):
        return ProviderInvalidKeyError(str(exc))
    if any(m in blob for m in _TRANSIENT_MARKERS):
        return ProviderTransientError(str(exc))
    return ProviderError(str(exc))


def _to_messages(messages: Sequence[dict[str, str]], *, system: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if system:
        out.append({"role": "system", "content": system})
    for msg in messages:
        role = msg.get("role", "user")
        if role not in ("user", "assistant", "system"):
            role = "user"
        out.append({"role": role, "content": msg.get("content", "")})
    return out


class GroqChatProvider:
    """``LLMProvider`` backed by ``groq`` (chat + streaming chat)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import groq  # lazy import (ADR-0006)

            self._client = groq.Groq(api_key=self._api_key)
        return self._client

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
            response = client.chat.completions.create(
                model=model,
                messages=_to_messages(messages, system=system),
                max_tokens=max_tokens,
            )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize SDK errors
            raise _translate_error(exc) from exc
        choice = response.choices[0]
        text = getattr(choice.message, "content", "") or ""
        usage = getattr(response, "usage", None)
        return ChatResult(
            text=text,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
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
            stream = client.chat.completions.create(
                model=model,
                messages=_to_messages(messages, system=system),
                max_tokens=max_tokens,
                stream=True,
            )
            for event in stream:
                choices = getattr(event, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                text = getattr(delta, "content", None) if delta is not None else None
                if text:
                    yield ChatDelta(text=text)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize SDK errors
            raise _translate_error(exc) from exc


__all__ = ["GroqChatProvider", "DEFAULT_CHAT_MODEL"]
