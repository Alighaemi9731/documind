"""Static provider registry (ADR-0006). Phase-2 slice registers Gemini only.

The registry is the lookup table from a ``Provider`` enum value to its
``ProviderSpec`` (the single source of truth). Adapter classes are imported
lazily via :func:`load_embedding_adapter` so a default install never imports an
unused SDK.
"""

from __future__ import annotations

import importlib

from app.models.enums import Capability, Provider
from app.providers.adapters.gemini import DEFAULT_DIM, DEFAULT_MODEL
from app.providers.interfaces import EmbeddingProvider
from app.providers.spec import ModelSpec, ProviderSpec

GEMINI_SPEC = ProviderSpec(
    id=Provider.google.value,
    label="Google Gemini",
    capabilities=(Capability.chat, Capability.embedding),
    chat=ModelSpec(model="gemini-2.0-flash", max_input_tokens=1_000_000),
    embedding=ModelSpec(
        model=DEFAULT_MODEL,
        dim=DEFAULT_DIM,
        normalized=True,
        max_input_tokens=2048,
    ),
    requires_byok=False,
    base_url="https://generativelanguage.googleapis.com",
    embedding_adapter="app.providers.adapters.gemini:GeminiEmbeddingProvider",
)

_REGISTRY: dict[str, ProviderSpec] = {
    GEMINI_SPEC.id: GEMINI_SPEC,
}


def get_spec(provider_id: str) -> ProviderSpec:
    """Return the ProviderSpec for ``provider_id`` or raise ``KeyError``."""
    return _REGISTRY[provider_id]


def list_specs() -> list[ProviderSpec]:
    """All registered provider specs."""
    return list(_REGISTRY.values())


def load_embedding_adapter(spec: ProviderSpec, api_key: str) -> EmbeddingProvider:
    """Lazily import + construct the embedding adapter for ``spec``.

    The adapter is constructed from the decrypted ``api_key`` string. The dim
    pin is passed so the adapter requests the right output dimensionality.
    """
    module_path, _, class_name = spec.embedding_adapter.partition(":")
    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    dim = spec.embedding.dim if spec.embedding is not None else DEFAULT_DIM
    adapter: EmbeddingProvider = adapter_cls(api_key, dim=dim)
    return adapter


__all__ = [
    "GEMINI_SPEC",
    "get_spec",
    "list_specs",
    "load_embedding_adapter",
]
