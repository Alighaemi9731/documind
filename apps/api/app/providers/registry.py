"""Static provider registry (ADR-0006). Single source of truth per provider.

Maps a ``Provider`` enum value to its ``ProviderSpec``. Adapter classes are
imported lazily via :func:`load_embedding_adapter` / :func:`load_chat_adapter`
so a default Gemini-only install never imports an unused SDK (openai / anthropic
/ groq / torch). Adding a provider is ONE spec row here plus one adapter file.

Capability matrix:
    google        chat + embedding (operator default; no BYOK required)
    openai        chat + embedding
    anthropic     chat-only  (no embeddings)
    groq          chat-only  (no embeddings)
    local_bge_m3  embedding-only (opt-in, worker process)

Selecting an unsupported ``(provider, capability)`` pair raises
:class:`CapabilityUnsupported` (the route maps it to HTTP 409).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

from app.models.enums import Capability, Provider
from app.providers.adapters import local_bge_m3 as _local
from app.providers.adapters.anthropic import DEFAULT_CHAT_MODEL as ANTHROPIC_CHAT_MODEL
from app.providers.adapters.gemini import DEFAULT_CHAT_MODEL, DEFAULT_DIM, DEFAULT_MODEL
from app.providers.adapters.groq import DEFAULT_CHAT_MODEL as GROQ_CHAT_MODEL
from app.providers.adapters.openai import (
    DEFAULT_CHAT_MODEL as OPENAI_CHAT_MODEL,
)
from app.providers.adapters.openai import (
    DEFAULT_EMBED_DIM as OPENAI_EMBED_DIM,
)
from app.providers.adapters.openai import (
    DEFAULT_EMBED_MODEL as OPENAI_EMBED_MODEL,
)
from app.providers.interfaces import EmbeddingProvider, LLMProvider
from app.providers.spec import ModelSpec, ProviderSpec


class CapabilityUnsupported(RuntimeError):
    """Selecting a (provider, capability) pair the provider does not offer (409)."""


GEMINI_SPEC = ProviderSpec(
    id=Provider.google.value,
    label="Google Gemini",
    capabilities=(Capability.chat, Capability.embedding),
    chat=ModelSpec(model=DEFAULT_CHAT_MODEL, max_input_tokens=1_000_000),
    embedding=ModelSpec(
        model=DEFAULT_MODEL,
        dim=DEFAULT_DIM,
        normalized=True,
        max_input_tokens=2048,
    ),
    requires_byok=False,
    base_url="https://generativelanguage.googleapis.com",
    embedding_adapter="app.providers.adapters.gemini:GeminiEmbeddingProvider",
    chat_adapter="app.providers.adapters.gemini:GeminiChatProvider",
    extra={"key_format_hint": "AIza... (Google AI Studio key)"},
)

OPENAI_SPEC = ProviderSpec(
    id=Provider.openai.value,
    label="OpenAI",
    capabilities=(Capability.chat, Capability.embedding),
    chat=ModelSpec(model=OPENAI_CHAT_MODEL, max_input_tokens=128_000),
    embedding=ModelSpec(
        model=OPENAI_EMBED_MODEL,
        dim=OPENAI_EMBED_DIM,
        normalized=True,
        max_input_tokens=8191,
    ),
    requires_byok=True,
    base_url="https://api.openai.com",
    embedding_adapter="app.providers.adapters.openai:OpenAIEmbeddingProvider",
    chat_adapter="app.providers.adapters.openai:OpenAIChatProvider",
    extra={"key_format_hint": "sk-... (OpenAI API key)"},
)

ANTHROPIC_SPEC = ProviderSpec(
    id=Provider.anthropic.value,
    label="Anthropic Claude",
    capabilities=(Capability.chat,),  # CHAT-ONLY: Anthropic has no embeddings.
    chat=ModelSpec(model=ANTHROPIC_CHAT_MODEL, max_input_tokens=1_000_000),
    embedding=None,
    requires_byok=True,
    base_url="https://api.anthropic.com",
    chat_adapter="app.providers.adapters.anthropic:AnthropicChatProvider",
    extra={"key_format_hint": "sk-ant-... (Anthropic API key)"},
)

GROQ_SPEC = ProviderSpec(
    id=Provider.groq.value,
    label="Groq",
    capabilities=(Capability.chat,),  # CHAT-ONLY.
    chat=ModelSpec(model=GROQ_CHAT_MODEL, max_input_tokens=128_000),
    embedding=None,
    requires_byok=True,
    base_url="https://api.groq.com",
    chat_adapter="app.providers.adapters.groq:GroqChatProvider",
    extra={"key_format_hint": "gsk_... (Groq API key)"},
)

LOCAL_BGE_M3_SPEC = ProviderSpec(
    id=Provider.local_bge_m3.value,
    label="Local bge-m3 (offline)",
    capabilities=(Capability.embedding,),  # EMBEDDING-ONLY.
    chat=None,
    embedding=ModelSpec(
        model=_local.MODEL_NAME,
        dim=_local.DEFAULT_DIM,
        normalized=True,
        max_input_tokens=8192,
    ),
    requires_byok=False,
    base_url="",  # local model: no network endpoint.
    embedding_adapter="app.providers.adapters.local_bge_m3:LocalBgeM3EmbeddingProvider",
    extra={"key_format_hint": "(no key — runs locally)"},
)

_REGISTRY: dict[str, ProviderSpec] = {
    GEMINI_SPEC.id: GEMINI_SPEC,
    OPENAI_SPEC.id: OPENAI_SPEC,
    ANTHROPIC_SPEC.id: ANTHROPIC_SPEC,
    GROQ_SPEC.id: GROQ_SPEC,
    LOCAL_BGE_M3_SPEC.id: LOCAL_BGE_M3_SPEC,
}


def get_spec(provider_id: str) -> ProviderSpec:
    """Return the ProviderSpec for ``provider_id`` or raise ``KeyError``."""
    return _REGISTRY[provider_id]


def register_spec(spec: ProviderSpec) -> None:
    """Register a spec (extensibility hook; one row adds a provider)."""
    _REGISTRY[spec.id] = spec


def list_specs() -> list[ProviderSpec]:
    """All registered provider specs."""
    return list(_REGISTRY.values())


def supports(provider_id: str, capability: Capability) -> bool:
    """True if ``provider_id`` offers ``capability``."""
    try:
        spec = get_spec(provider_id)
    except KeyError:
        return False
    return capability in spec.capabilities


def assert_supports(provider_id: str, capability: Capability) -> ProviderSpec:
    """Return the spec, raising :class:`CapabilityUnsupported` if it can't serve ``capability``."""
    try:
        spec = get_spec(provider_id)
    except KeyError as exc:
        raise CapabilityUnsupported(f"Unknown provider {provider_id!r}.") from exc
    if capability not in spec.capabilities:
        raise CapabilityUnsupported(
            f"Provider {provider_id!r} does not support capability {capability.value!r}."
        )
    return spec


def load_embedding_adapter(spec: ProviderSpec, api_key: str) -> EmbeddingProvider:
    """Lazily import + construct the embedding adapter for ``spec``."""
    if not spec.embedding_adapter:
        raise CapabilityUnsupported(f"{spec.id} has no embedding adapter.")
    module_path, _, class_name = spec.embedding_adapter.partition(":")
    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    dim = spec.embedding.dim if spec.embedding is not None else DEFAULT_DIM
    adapter: EmbeddingProvider = adapter_cls(api_key, dim=dim)
    return adapter


def load_chat_adapter(spec: ProviderSpec, api_key: str) -> LLMProvider:
    """Lazily import + construct the chat adapter for ``spec``."""
    if not spec.chat_adapter:
        raise CapabilityUnsupported(f"{spec.id} has no chat adapter.")
    module_path, _, class_name = spec.chat_adapter.partition(":")
    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    adapter: LLMProvider = adapter_cls(api_key)
    return adapter


def build_validation_probe(spec: ProviderSpec, api_key: str) -> Callable[[], None]:
    """Return a zero-arg cheap health check for ``spec`` (one provider call).

    Prefers the chat capability (a 1-token request) and falls back to embedding.
    Local providers (no base URL / no key) validate trivially as OK.
    """
    if not spec.base_url:
        # Local provider: nothing to reach; treat as valid.
        return lambda: None

    if spec.chat is not None and spec.chat_adapter:
        adapter = load_chat_adapter(spec, api_key)
        model = spec.chat.model

        def _probe_chat() -> None:
            adapter.chat(
                [{"role": "user", "content": "ping"}],
                model=model,
                system="",
                max_tokens=1,
            )

        return _probe_chat

    if spec.embedding is not None and spec.embedding_adapter:
        emb = load_embedding_adapter(spec, api_key)
        model = spec.embedding.model

        def _probe_embed() -> None:
            emb.embed_query("ping", model=model)

        return _probe_embed

    raise CapabilityUnsupported(f"{spec.id} has no probeable capability.")


__all__ = [
    "GEMINI_SPEC",
    "OPENAI_SPEC",
    "ANTHROPIC_SPEC",
    "GROQ_SPEC",
    "LOCAL_BGE_M3_SPEC",
    "CapabilityUnsupported",
    "get_spec",
    "register_spec",
    "list_specs",
    "supports",
    "assert_supports",
    "load_embedding_adapter",
    "load_chat_adapter",
    "build_validation_probe",
]
