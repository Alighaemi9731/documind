"""``ProviderSpec`` — the single source of truth for a provider (ADR-0006).

Read by the resolver, ingestion (embedding pin), settings UI, and admin. Base
URLs are part of the spec and never user-supplied (no SSRF). The Phase-2 slice
only populates Gemini (registry.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import Capability


@dataclass(frozen=True)
class ModelSpec:
    """A single model offered by a provider for one capability."""

    model: str
    # dim/normalized are meaningful for embedding models; for chat models the
    # dim is 0 and normalized is False (unused).
    dim: int = 0
    normalized: bool = False
    max_input_tokens: int = 0


@dataclass(frozen=True)
class ProviderSpec:
    """Everything the app needs to know about a provider, declaratively."""

    id: str
    label: str
    capabilities: tuple[Capability, ...]
    chat: ModelSpec | None = None
    embedding: ModelSpec | None = None
    requires_byok: bool = False
    base_url: str = ""
    # Dotted path to the adapter module + class, imported lazily on first use.
    embedding_adapter: str = ""
    extra: dict[str, str] = field(default_factory=dict)


__all__ = ["ModelSpec", "ProviderSpec"]
