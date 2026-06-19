"""GeminiChatProvider: contents mapping, streaming, error normalization."""

from __future__ import annotations

import sys
import types

import pytest

from app.providers.adapters.gemini import GeminiChatProvider
from app.providers.errors import ProviderAuthError, ProviderTransientError


def _install_fake_genai(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict,
    *,
    stream_texts: list[str] | None = None,
    raise_exc: Exception | None = None,
) -> None:
    class _Config:
        def __init__(self, *, system_instruction, max_output_tokens):  # noqa: ANN001
            self.system_instruction = system_instruction
            self.max_output_tokens = max_output_tokens

    class _Event:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Response:
        text = "full answer"
        usage_metadata = types.SimpleNamespace(
            prompt_token_count=11, candidates_token_count=7
        )

    class _Models:
        def generate_content(self, *, model, contents, config):  # noqa: ANN001
            if raise_exc is not None:
                raise raise_exc
            captured["model"] = model
            captured["contents"] = contents
            captured["system"] = config.system_instruction
            return _Response()

        def generate_content_stream(self, *, model, contents, config):  # noqa: ANN001
            if raise_exc is not None:
                raise raise_exc
            captured["contents"] = contents
            captured["system"] = config.system_instruction
            for t in stream_texts or []:
                yield _Event(t)

    class _Client:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key
            self.models = _Models()

    genai_mod = types.ModuleType("google.genai")
    genai_mod.Client = _Client  # type: ignore[attr-defined]
    types_mod = types.ModuleType("google.genai.types")
    types_mod.GenerateContentConfig = _Config  # type: ignore[attr-defined]
    google_mod = types.ModuleType("google")
    google_mod.genai = genai_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)


def test_chat_maps_roles_and_returns_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_genai(monkeypatch, captured)
    provider = GeminiChatProvider("k")
    result = provider.chat(
        [{"role": "user", "content": "hi"}],
        model="gemini-2.0-flash",
        system="SYS",
        max_tokens=100,
    )
    assert result.text == "full answer"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert captured["system"] == "SYS"
    assert captured["contents"][0]["role"] == "user"


def test_chat_stream_yields_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_genai(monkeypatch, captured, stream_texts=["Hel", "lo", " world"])
    provider = GeminiChatProvider("k")
    deltas = list(
        provider.chat_stream(
            [{"role": "user", "content": "hi"}],
            model="m",
            system="SYS",
            max_tokens=50,
        )
    )
    assert "".join(d.text for d in deltas) == "Hello world"


def test_assistant_role_maps_to_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_genai(monkeypatch, captured)
    provider = GeminiChatProvider("k")
    provider.chat(
        [{"role": "assistant", "content": "prior"}],
        model="m",
        system="s",
        max_tokens=10,
    )
    assert captured["contents"][0]["role"] == "model"


def test_auth_error_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_genai(
        monkeypatch, captured, raise_exc=RuntimeError("403 PERMISSION_DENIED: bad key")
    )
    provider = GeminiChatProvider("k")
    with pytest.raises(ProviderAuthError):
        provider.chat([{"role": "user", "content": "x"}], model="m", system="s", max_tokens=1)


def test_transient_error_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_genai(
        monkeypatch, captured, raise_exc=RuntimeError("429 RESOURCE_EXHAUSTED")
    )
    provider = GeminiChatProvider("k")
    with pytest.raises(ProviderTransientError):
        list(
            provider.chat_stream(
                [{"role": "user", "content": "x"}], model="m", system="s", max_tokens=1
            )
        )
