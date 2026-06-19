"""Registry: capability matrix + one-spec-row extensibility (ADR-0006).

Asserts the chat-only / embedding-only markers, the CapabilityUnsupported guard,
and that adding a synthetic provider is a single ``register_spec`` call that
immediately participates in lookup + capability checks."""

from __future__ import annotations

import pytest

from app.models.enums import Capability
from app.providers import registry
from app.providers.spec import ModelSpec, ProviderSpec


def test_capability_matrix() -> None:
    assert registry.supports("openai", Capability.chat)
    assert registry.supports("openai", Capability.embedding)
    assert registry.supports("anthropic", Capability.chat)
    assert not registry.supports("anthropic", Capability.embedding)  # chat-only
    assert registry.supports("groq", Capability.chat)
    assert not registry.supports("groq", Capability.embedding)  # chat-only
    assert registry.supports("local_bge_m3", Capability.embedding)
    assert not registry.supports("local_bge_m3", Capability.chat)  # embedding-only


def test_assert_supports_raises_for_unsupported() -> None:
    with pytest.raises(registry.CapabilityUnsupported):
        registry.assert_supports("anthropic", Capability.embedding)
    with pytest.raises(registry.CapabilityUnsupported):
        registry.assert_supports("local_bge_m3", Capability.chat)


def test_anthropic_uses_opus_48() -> None:
    spec = registry.get_spec("anthropic")
    assert spec.chat is not None
    assert spec.chat.model == "claude-opus-4-8"
    assert spec.embedding is None  # no embeddings


def test_add_synthetic_provider_is_one_row() -> None:
    synthetic = ProviderSpec(
        id="synthetic_test_provider",
        label="Synthetic",
        capabilities=(Capability.chat,),
        chat=ModelSpec(model="synthetic-chat-1", max_input_tokens=8192),
        requires_byok=True,
        base_url="https://synthetic.example",
        chat_adapter="app.providers.adapters.openai:OpenAIChatProvider",
    )
    try:
        registry.register_spec(synthetic)
        assert registry.get_spec("synthetic_test_provider") is synthetic
        assert registry.supports("synthetic_test_provider", Capability.chat)
        assert synthetic in registry.list_specs()
    finally:
        # Clean up the synthetic row so other tests see the canonical registry.
        registry._REGISTRY.pop("synthetic_test_provider", None)
