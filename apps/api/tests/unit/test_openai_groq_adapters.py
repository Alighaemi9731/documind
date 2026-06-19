"""OpenAI + Groq adapter conformance with a STUBBED SDK (no network).

Asserts the chat/embedding surface maps to the SDK shape, default models/dims,
streaming deltas, and that SDK exceptions normalize into the provider taxonomy.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.providers.adapters.groq import GroqChatProvider
from app.providers.adapters.openai import (
    DEFAULT_EMBED_DIM,
    OpenAIChatProvider,
    OpenAIEmbeddingProvider,
)
from app.providers.errors import ProviderInvalidKeyError, ProviderTransientError


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)
        self.delta = _Msg(content)


class _Usage:
    prompt_tokens = 5
    completion_tokens = 3


class _Resp:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]
        self.usage = _Usage()


class _EmbItem:
    def __init__(self, vec: list[float]) -> None:
        self.embedding = vec


class _EmbResp:
    def __init__(self, vecs: list[list[float]]) -> None:
        self.data = [_EmbItem(v) for v in vecs]


def _install_openai(
    monkeypatch: pytest.MonkeyPatch, captured: dict, *, raise_exc: Exception | None = None
) -> None:
    class _Completions:
        def create(self, **kwargs):  # noqa: ANN003
            if raise_exc is not None:
                raise raise_exc
            captured["chat_kwargs"] = kwargs
            if kwargs.get("stream"):
                return iter([_StreamEvent("Hel"), _StreamEvent("lo")])
            return _Resp("hi there")

    class _Embeddings:
        def create(self, **kwargs):  # noqa: ANN003
            if raise_exc is not None:
                raise raise_exc
            captured["embed_kwargs"] = kwargs
            return _EmbResp([[0.1] * DEFAULT_EMBED_DIM for _ in kwargs["input"]])

    class _StreamEvent:
        def __init__(self, text: str) -> None:
            self.choices = [_Choice(text)]

    class _Client:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key
            self.chat = types.SimpleNamespace(completions=_Completions())
            self.embeddings = _Embeddings()

    mod = types.ModuleType("openai")
    mod.OpenAI = _Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", mod)


def test_openai_chat_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_openai(monkeypatch, captured)
    provider = OpenAIChatProvider("sk-x")
    result = provider.chat(
        [{"role": "user", "content": "q"}], model="gpt-4o-mini", system="S", max_tokens=10
    )
    assert result.text == "hi there"
    assert result.input_tokens == 5 and result.output_tokens == 3
    # System turn is prepended.
    assert captured["chat_kwargs"]["messages"][0] == {"role": "system", "content": "S"}


def test_openai_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_openai(monkeypatch, captured)
    provider = OpenAIChatProvider("sk-x")
    deltas = list(
        provider.chat_stream([{"role": "user", "content": "q"}], model="m", system="", max_tokens=5)
    )
    assert "".join(d.text for d in deltas) == "Hello"


def test_openai_embeddings_dim(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_openai(monkeypatch, captured)
    provider = OpenAIEmbeddingProvider("sk-x")
    vecs = provider.embed_documents(["a", "b"], model="text-embedding-3-small")
    assert len(vecs) == 2
    assert all(len(v) == DEFAULT_EMBED_DIM for v in vecs)
    assert provider.dimension("text-embedding-3-small") == DEFAULT_EMBED_DIM


def test_openai_auth_error_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_openai(monkeypatch, captured, raise_exc=RuntimeError("401 invalid api key"))
    provider = OpenAIChatProvider("sk-x")
    with pytest.raises(ProviderInvalidKeyError):
        provider.chat([{"role": "user", "content": "q"}], model="m", system="", max_tokens=1)


def _install_groq(
    monkeypatch: pytest.MonkeyPatch, captured: dict, *, raise_exc: Exception | None = None
) -> None:
    class _StreamEvent:
        def __init__(self, text: str) -> None:
            self.choices = [_Choice(text)]

    class _Completions:
        def create(self, **kwargs):  # noqa: ANN003
            if raise_exc is not None:
                raise raise_exc
            captured["chat_kwargs"] = kwargs
            if kwargs.get("stream"):
                return iter([_StreamEvent("Go"), _StreamEvent("!")])
            return _Resp("groq says hi")

    class _Client:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key
            self.chat = types.SimpleNamespace(completions=_Completions())

    mod = types.ModuleType("groq")
    mod.Groq = _Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "groq", mod)


def test_groq_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_groq(monkeypatch, captured)
    provider = GroqChatProvider("gsk_x")
    result = provider.chat(
        [{"role": "user", "content": "q"}],
        model="llama-3.3-70b-versatile",
        system="S",
        max_tokens=10,
    )
    assert result.text == "groq says hi"


def test_groq_transient_error_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_groq(monkeypatch, captured, raise_exc=RuntimeError("503 service unavailable"))
    provider = GroqChatProvider("gsk_x")
    with pytest.raises(ProviderTransientError):
        list(
            provider.chat_stream(
                [{"role": "user", "content": "q"}], model="m", system="", max_tokens=1
            )
        )
