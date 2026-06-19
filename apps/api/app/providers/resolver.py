"""Per-capability two-tier provider resolver (ADR-0006, ARCHITECTURE.md section 6).

Order, per capability and INDEPENDENT across capabilities:
  1. the user's active BYOK credential + selection for THIS capability
     -> ``key_source = byok`` (a BYOK chat=OpenAI may coexist with shared Gemini
     embeddings);
  2. else the operator default (Gemini) -> ``key_source = shared``.

For ``capability=embedding`` with a ``project_id`` the resolved
``(provider, model, dim)`` MUST equal the project's immutable embedding pin
(ADR-0003/0015); a mismatch raises :class:`EmbeddingPinMismatch` (409). The BYOK
key is decrypted via the keystore and the adapter is constructed via the registry
(lazy SDK import). The ``set_*_override`` hooks let tests inject deterministic
fakes so no real network call happens.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Capability, KeySource
from app.models.project import Project
from app.models.provider_key import ProviderKey
from app.models.provider_selection import ProviderSelection
from app.providers import registry
from app.providers.interfaces import EmbeddingProvider, LLMProvider
from app.providers.keystore import store as keystore
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
    """Install (or clear) a process-wide chat adapter override for tests."""
    global _chat_override
    _chat_override = provider


@dataclass(frozen=True)
class ResolvedProvider:
    """The outcome of resolution for the embedding capability."""

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
    """The resolved provider does not offer the requested capability."""


def default_embedding_spec() -> ProviderSpec:
    """The operator-default embedding provider spec (Gemini)."""
    return registry.GEMINI_SPEC


def default_chat_spec() -> ProviderSpec:
    """The operator-default chat provider spec (Gemini)."""
    return registry.GEMINI_SPEC


async def _load_project_pin(session: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProviderResolutionError("Project not found for embedding resolution.")
    return project


async def _load_selection(
    session: AsyncSession, user_id: uuid.UUID, capability: Capability
) -> ProviderSelection | None:
    result = await session.execute(
        select(ProviderSelection).where(
            ProviderSelection.user_id == user_id,
            ProviderSelection.capability == capability.value,
        )
    )
    return result.scalar_one_or_none()


async def _byok_credential(session: AsyncSession, user_id: uuid.UUID, provider_id: str):  # noqa: ANN202 - returns ProviderKey | None
    result = await session.execute(
        select(ProviderKey).where(
            ProviderKey.user_id == user_id,
            ProviderKey.provider == provider_id,
            ProviderKey.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


def _assert_pin(project: Project, *, provider_id: str, model: str, dim: int) -> None:
    if (
        project.embedding_provider != provider_id
        or project.embedding_model != model
        or project.embedding_dim != dim
    ):
        raise EmbeddingPinMismatch("Resolved embedding identity does not match the project pin.")


async def resolve(
    session: AsyncSession,
    user_id: uuid.UUID,
    capability: Capability,
    project_id: uuid.UUID | None = None,
) -> ResolvedProvider:
    """Resolve a provider for the embedding ``capability`` (BYOK -> shared).

    For the embedding capability with a ``project_id`` the resolved identity is
    asserted against the project pin (BYOK and shared alike).
    """
    if capability is not Capability.embedding:
        raise UnsupportedCapability("resolve() handles only the embedding capability.")

    # --- TIER 1: BYOK (selection + active credential for THIS capability). ---
    byok = await _resolve_byok_embedding(session, user_id, project_id)
    if byok is not None:
        return byok

    # --- TIER 2: shared operator default (Gemini). ---
    spec = default_embedding_spec()
    if spec.embedding is None:
        raise UnsupportedCapability(f"{spec.id} does not offer an embedding model.")
    model = spec.embedding.model
    dim = spec.embedding.dim

    if project_id is not None:
        project = await _load_project_pin(session, project_id)
        _assert_pin(project, provider_id=spec.id, model=model, dim=dim)

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


async def _resolve_byok_embedding(
    session: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID | None,
) -> ResolvedProvider | None:
    selection = await _load_selection(session, user_id, Capability.embedding)
    if selection is None:
        return None
    try:
        spec = registry.assert_supports(selection.provider, Capability.embedding)
    except registry.CapabilityUnsupported:
        return None
    if spec.embedding is None:
        return None

    credential = await _byok_credential(session, user_id, selection.provider)
    if credential is None:
        return None

    model = selection.model
    dim = spec.embedding.dim

    if project_id is not None:
        project = await _load_project_pin(session, project_id)
        _assert_pin(project, provider_id=spec.id, model=model, dim=dim)

    if _embedding_override is not None:
        adapter: EmbeddingProvider = _embedding_override
    else:
        secret = await keystore.load_user_key(session, user_id=user_id, provider=selection.provider)
        if secret is None:
            return None
        adapter = registry.load_embedding_adapter(spec, secret.reveal())

    return ResolvedProvider(
        adapter=adapter,
        model=model,
        key_source=KeySource.byok,
        dim=dim,
        provider_id=spec.id,
    )


async def resolve_chat(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> ResolvedChatProvider:
    """Resolve the chat provider (capability=chat): BYOK -> shared."""
    # --- TIER 1: BYOK chat. ---
    byok = await _resolve_byok_chat(session, user_id)
    if byok is not None:
        return byok

    # --- TIER 2: shared operator default (Gemini). ---
    spec = default_chat_spec()
    if spec.chat is None:
        raise UnsupportedCapability(f"{spec.id} does not offer a chat model.")
    model = spec.chat.model

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


async def _resolve_byok_chat(
    session: AsyncSession, user_id: uuid.UUID
) -> ResolvedChatProvider | None:
    selection = await _load_selection(session, user_id, Capability.chat)
    if selection is None:
        return None
    try:
        spec = registry.assert_supports(selection.provider, Capability.chat)
    except registry.CapabilityUnsupported:
        return None
    if spec.chat is None:
        return None

    credential = await _byok_credential(session, user_id, selection.provider)
    if credential is None:
        return None

    if _chat_override is not None:
        adapter: LLMProvider = _chat_override
    else:
        secret = await keystore.load_user_key(session, user_id=user_id, provider=selection.provider)
        if secret is None:
            return None
        adapter = registry.load_chat_adapter(spec, secret.reveal())

    return ResolvedChatProvider(
        adapter=adapter,
        model=selection.model,
        key_source=KeySource.byok,
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
