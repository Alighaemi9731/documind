"""Anthropic chat adapter using the official ``anthropic`` SDK ONLY (ADR-0010).

No hand-rolled HTTP. Conventions (authoritative — see the ``claude-api`` skill):

* model ``claude-opus-4-8``
* ``thinking={"type": "adaptive"}`` (adaptive is the only on-mode on Opus 4.8)
* streaming via ``client.messages.stream(...)`` iterating text deltas, with
  ``stream.get_final_message()`` for usage; non-stream via
  ``client.messages.create(...)``
* ``max_tokens`` is REQUIRED; the system prompt is passed via the ``system`` param
* NEVER send ``budget_tokens`` / ``temperature`` / ``top_p`` / ``top_k`` — all of
  these return HTTP 400 on Opus 4.8, so they are not passed under any code path.

Anthropic has NO embeddings, so this module is CHAT-ONLY (the embedding
capability is unsupported in the registry). The SDK is lazily imported (ADR-0006)
and exceptions are normalized into :mod:`app.providers.errors`. Tests inject a
stubbed ``anthropic`` module so no real network call happens.
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

DEFAULT_CHAT_MODEL = "claude-opus-4-8"
# Adaptive thinking — the ONLY valid on-mode on Opus 4.8 (ADR-0010).
THINKING = {"type": "adaptive"}

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
    "authentication",
    "invalid x-api-key",
    "invalid api key",
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


def _to_messages(messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    """Map app messages to the Anthropic schema (user/assistant only).

    The system prompt is passed separately via the ``system`` param, never as a
    message; any stray ``system`` role is folded into ``user``.
    """
    out: list[dict[str, str]] = []
    for msg in messages:
        role = "assistant" if msg.get("role") == "assistant" else "user"
        out.append({"role": role, "content": msg.get("content", "")})
    return out


class AnthropicChatProvider:
    """``LLMProvider`` backed by the official ``anthropic`` SDK (chat-only)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # lazy import (ADR-0006)

            self._client = anthropic.Anthropic(api_key=self._api_key)
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
            # NOTE: only model/max_tokens/system/thinking/messages are passed —
            # NEVER budget_tokens/temperature/top_p/top_k (400 on Opus 4.8).
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                thinking=THINKING,
                messages=_to_messages(messages),
            )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize SDK errors
            raise _translate_error(exc) from exc
        text = _text_from_blocks(getattr(message, "content", None))
        usage = getattr(message, "usage", None)
        return ChatResult(
            text=text,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
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
            # Stream via messages.stream(...); iterate text deltas; usage is read
            # from get_final_message() after the stream is drained.
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                thinking=THINKING,
                messages=_to_messages(messages),
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        yield ChatDelta(text=text)
                # Drain final usage; not yielded but exercised for completeness.
                stream.get_final_message()
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize SDK errors
            raise _translate_error(exc) from exc


def _text_from_blocks(content: Any) -> str:
    """Concatenate ``text`` blocks from an Anthropic message ``content`` list."""
    if content is None:
        return ""
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    return "".join(parts)


__all__ = ["AnthropicChatProvider", "DEFAULT_CHAT_MODEL", "THINKING"]
