"""AnthropicChatProvider: official SDK, claude-opus-4-8, adaptive thinking, and
NO budget_tokens/temperature/top_p/top_k (ADR-0010). Uses a stubbed ``anthropic``
module so no real network call happens (no key locally)."""

from __future__ import annotations

import sys
import types

import pytest

from app.providers.adapters.anthropic import (
    DEFAULT_CHAT_MODEL,
    AnthropicChatProvider,
)
from app.providers.errors import ProviderInvalidKeyError, ProviderTransientError

_FORBIDDEN = ("budget_tokens", "temperature", "top_p", "top_k")


class _TextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Usage:
    input_tokens = 13
    output_tokens = 7


class _Message:
    content = [_TextBlock("full answer")]
    usage = _Usage()


class _Stream:
    def __init__(self, texts: list[str]) -> None:
        self.text_stream = iter(texts)
        self.final_called = False

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        return None

    def get_final_message(self) -> _Message:
        self.final_called = True
        return _Message()


def _install_fake_anthropic(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict,
    *,
    stream_texts: list[str] | None = None,
    raise_exc: Exception | None = None,
) -> None:
    class _Messages:
        def create(self, **kwargs):  # noqa: ANN003
            if raise_exc is not None:
                raise raise_exc
            captured["create_kwargs"] = kwargs
            return _Message()

        def stream(self, **kwargs):  # noqa: ANN003
            if raise_exc is not None:
                raise raise_exc
            captured["stream_kwargs"] = kwargs
            return _Stream(stream_texts or [])

    class _Client:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key
            self.messages = _Messages()

    mod = types.ModuleType("anthropic")
    mod.Anthropic = _Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", mod)


def test_chat_uses_opus_48_adaptive_no_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_anthropic(monkeypatch, captured)
    provider = AnthropicChatProvider("k")
    result = provider.chat(
        [{"role": "user", "content": "hi"}],
        model=DEFAULT_CHAT_MODEL,
        system="SYS",
        max_tokens=256,
    )
    kwargs = captured["create_kwargs"]
    assert DEFAULT_CHAT_MODEL == "claude-opus-4-8"
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["system"] == "SYS"
    assert kwargs["max_tokens"] == 256
    for forbidden in _FORBIDDEN:
        assert forbidden not in kwargs
    assert result.text == "full answer"
    assert result.input_tokens == 13
    assert result.output_tokens == 7


def test_chat_stream_yields_deltas_and_no_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    _install_fake_anthropic(monkeypatch, captured, stream_texts=["Hel", "lo", " world"])
    provider = AnthropicChatProvider("k")
    deltas = list(
        provider.chat_stream(
            [{"role": "user", "content": "hi"}],
            model=DEFAULT_CHAT_MODEL,
            system="SYS",
            max_tokens=512,
        )
    )
    assert "".join(d.text for d in deltas) == "Hello world"
    kwargs = captured["stream_kwargs"]
    assert kwargs["thinking"] == {"type": "adaptive"}
    for forbidden in _FORBIDDEN:
        assert forbidden not in kwargs


def test_auth_error_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_anthropic(monkeypatch, captured, raise_exc=RuntimeError("401 invalid x-api-key"))
    provider = AnthropicChatProvider("k")
    with pytest.raises(ProviderInvalidKeyError):
        provider.chat([{"role": "user", "content": "x"}], model="m", system="", max_tokens=1)


def test_transient_error_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_anthropic(monkeypatch, captured, raise_exc=RuntimeError("429 overloaded"))
    provider = AnthropicChatProvider("k")
    with pytest.raises(ProviderTransientError):
        list(
            provider.chat_stream(
                [{"role": "user", "content": "x"}], model="m", system="", max_tokens=1
            )
        )
