"""Per-capability two-tier provider resolver (ADR-0006, ARCHITECTURE.md section 6).

Phase-2 implements only the **operator-default (shared)** tier for the embedding
capability; the BYOK tier lands in Phase 4 and slots in ahead of the shared
branch without changing this function's shape (``key_source`` already carries
the distinction).

For ``capability=embedding`` with a ``project_id`` the resolved
``(provider, model, dim)`` must equal the project's immutable embedding pin
(ADR-0003/0015); a mismatch raises :class:`EmbeddingPinMismatch`, surfaced as
HTTP 409 by the route layer.

A process-level override hook (:func:`set_embedding_override`) lets tests inject
a deterministic ``FakeEmbeddingProvider`` so no real network call happens.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Capability, KeySource
from app.models.project import Project
from app.providers import registry
from app.providers.interfaces import EmbeddingProvider, LLMProvider
from app.providers.keystore.operator_default import load_operator_key
from app.providers.spec import ProviderSpec

# --------------------------------------------------------------------------- #
# Test override hooks (process-level). Never set in production.
# --------------------------------------------------------------------------- #
_embedding_override: EmbeddingProvider | None = None
_chat_override: LLMProvider | None = None


def set_embedding_override(provider: EmbeddingProvider | None) -> None:
    """Install (or clear) a process-wide embedding adapter override for tests."""
    global _embedding_override
    _embedding_override = provider


def set_chat_override(provider: LLMProvider | None) -> None:
    """Install (or clear) a process-wide chat adapter override for tests.

    Lets a deterministic streaming chat fake (emitting a chosen answer +
    sentinel) be injected so the RAG answer path runs with no real network
    call (no GEMINI key locally).
    """
    global _chat_override
    _chat_override = provider


@dataclass(frozen=True)
class ResolvedProvider:
    """The outcome of resolution for one capability."""

    adapter: EmbeddingProvider
    model: str
    key_source: KeySource
    dim: int
    provider_id: str


@dataclass(frozen=True)
class ResolvedChatProvider:
    """The outcome of resolving the chat capability."""

    adapter: LLMProvider
    model: str
    key_source: KeySource
    provider_id: str


class ProviderResolutionError(RuntimeError):
    """Base class for resolver failures (typed for the route layer)."""


class EmbeddingPinMismatch(ProviderResolutionError):
    """Resolved embedding identity != the project's pinned identity (409)."""


class UnsupportedCapability(ProviderResolutionError):
    """The default provider does not offer the requested capability."""


def default_embedding_spec() -> ProviderSpec:
    """The operator-default embedding provider spec (Gemini in Phase 2)."""
    return registry.GEMINI_SPEC


def default_chat_spec() -> ProviderSpec:
    """The operator-default chat provider spec (Gemini in Phase 3)."""
    return registry.GEMINI_SPEC


async def _load_project_pin(session: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProviderResolutionError("Project not found for embedding resolution.")
    return project


async def resolve(
    session: AsyncSession,
    user_id: uuid.UUID,
    capability: Capability,
    project_id: uuid.UUID | None = None,
) -> ResolvedProvider:
    """Resolve a provider for ``capability``.

    Phase-2 path: operator default only (``key_source='shared'``). For the
    embedding capability with a ``project_id`` the resolved identity is asserted
    against the project pin.
    """
    if capability is not Capability.embedding:
        # Chat resolution lands with the RAG core (Phase 3); not in this slice.
        raise UnsupportedCapability("Only the embedding capability is resolvable in Phase 2.")

    spec = default_embedding_spec()
    if spec.embedding is None:
        raise UnsupportedCapability(f"{spec.id} does not offer an embedding model.")

    model = spec.embedding.model
    dim = spec.embedding.dim

    if project_id is not None:
        project = await _load_project_pin(session, project_id)
        if (
            project.embedding_provider != spec.id
            or project.embedding_model != model
            or project.embedding_dim != dim
        ):
            raise EmbeddingPinMismatch(
                "Resolved embedding identity does not match the project pin."
            )

    # --- TIER 1 (Phase 4): BYOK. Slots in here ahead of the shared branch. ---
    # if byok := await _resolve_byok(session, user_id, capability): return byok

    # --- TIER 2: shared operator default. ---
    if _embedding_override is not None:
        adapter: EmbeddingProvider = _embedding_override
    else:
        secret = await load_operator_key(session, provider=spec.id)
        adapter = registry.load_embedding_adapter(spec, secret.reveal())

    return ResolvedProvider(
        adapter=adapter,
        model=model,
        key_source=KeySource.shared,
        dim=dim,
        provider_id=spec.id,
    )


async def resolve_chat(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> ResolvedChatProvider:
    """Resolve the chat provider (capability=chat).

    Phase-3 path: operator default only (Gemini, ``key_source='shared'``). The
    BYOK tier (Phase 4) slots in ahead of the shared branch without changing the
    return shape. A process-level chat override lets tests inject a deterministic
    streaming fake so no real network call happens.
    """
    spec = default_chat_spec()
    if spec.chat is None:
        raise UnsupportedCapability(f"{spec.id} does not offer a chat model.")

    model = spec.chat.model

    # --- TIER 1 (Phase 4): BYOK chat. Slots in here ahead of the shared branch.
    # if byok := await _resolve_byok_chat(session, user_id): return byok

    # --- TIER 2: shared operator default. ---
    if _chat_override is not None:
        adapter: LLMProvider = _chat_override
    else:
        secret = await load_operator_key(session, provider=spec.id)
        adapter = registry.load_chat_adapter(spec, secret.reveal())

    return ResolvedChatProvider(
        adapter=adapter,
        model=model,
        key_source=KeySource.shared,
        provider_id=spec.id,
    )


__all__ = [
    "ResolvedProvider",
    "ResolvedChatProvider",
    "ProviderResolutionError",
    "EmbeddingPinMismatch",
    "UnsupportedCapability",
    "resolve",
    "resolve_chat",
    "set_embedding_override",
    "set_chat_override",
    "default_embedding_spec",
    "default_chat_spec",
]
