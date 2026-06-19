"""Gemini adapter: manual L2-normalize math + embed flow with a stubbed SDK."""

from __future__ import annotations

import math
import sys
import types

import pytest

from app.providers.adapters.gemini import (
    DEFAULT_DIM,
    TASK_DOCUMENT,
    TASK_QUERY,
    GeminiEmbeddingProvider,
    l2_normalize,
)


def test_l2_normalize_unit_length() -> None:
    out = l2_normalize([3.0, 4.0])
    assert out == [0.6, 0.8]
    assert math.isclose(math.sqrt(sum(x * x for x in out)), 1.0)


def test_l2_normalize_zero_vector_safe() -> None:
    assert l2_normalize([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


def _install_fake_genai(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    """Install a stub ``google.genai`` + ``google.genai.types`` in sys.modules."""

    class _Embedding:
        def __init__(self, values: list[float]) -> None:
            self.values = values

    class _Result:
        def __init__(self, embeddings: list[_Embedding]) -> None:
            self.embeddings = embeddings

    class _Models:
        def embed_content(self, *, model, contents, config):  # noqa: ANN001
            captured["model"] = model
            captured["contents"] = contents
            captured["task_type"] = config.task_type
            captured["dim"] = config.output_dimensionality
            # Return un-normalized vectors so we can assert normalization.
            return _Result([_Embedding([3.0, 4.0] + [0.0] * (DEFAULT_DIM - 2)) for _ in contents])

    class _Client:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key
            self.models = _Models()

    class _EmbedConfig:
        def __init__(self, *, task_type, output_dimensionality):  # noqa: ANN001
            self.task_type = task_type
            self.output_dimensionality = output_dimensionality

    genai_mod = types.ModuleType("google.genai")
    genai_mod.Client = _Client  # type: ignore[attr-defined]
    types_mod = types.ModuleType("google.genai.types")
    types_mod.EmbedContentConfig = _EmbedConfig  # type: ignore[attr-defined]
    google_mod = types.ModuleType("google")
    google_mod.genai = genai_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)


def test_embed_documents_normalizes_and_sends_task_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    _install_fake_genai(monkeypatch, captured)

    provider = GeminiEmbeddingProvider("secret-key")
    vectors = provider.embed_documents(["hello", "world"], model="gemini-embedding-001")

    assert captured["api_key"] == "secret-key"
    assert captured["task_type"] == TASK_DOCUMENT
    assert captured["dim"] == DEFAULT_DIM
    assert len(vectors) == 2
    # 3,4 -> normalized 0.6, 0.8.
    assert math.isclose(vectors[0][0], 0.6)
    assert math.isclose(vectors[0][1], 0.8)
    assert math.isclose(math.sqrt(sum(x * x for x in vectors[0])), 1.0)


def test_embed_query_uses_query_task(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_genai(monkeypatch, captured)
    provider = GeminiEmbeddingProvider("k")
    vec = provider.embed_query("a question", model="gemini-embedding-001")
    assert captured["task_type"] == TASK_QUERY
    assert len(vec) == DEFAULT_DIM


def test_embed_documents_empty_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _install_fake_genai(monkeypatch, captured)
    provider = GeminiEmbeddingProvider("k")
    assert provider.embed_documents([], model="m") == []
    assert "task_type" not in captured  # SDK never called
