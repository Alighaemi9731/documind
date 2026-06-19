"""Resolver unit tests: shared-tier precedence + embedding-dim pin assert.

Uses the process-level override hook so no operator key / network is needed, and
a minimal fake session that returns a project row for the pin check.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import Capability
from app.providers import resolver
from app.providers.registry import GEMINI_SPEC
from tests.fakes import FakeEmbeddingProvider

pytestmark = pytest.mark.asyncio


class _FakeProject:
    def __init__(self, *, provider: str, model: str, dim: int) -> None:
        self.id = uuid.uuid4()
        self.embedding_provider = provider
        self.embedding_model = model
        self.embedding_dim = dim


class _FakeResult:
    def __init__(self, obj: object) -> None:
        self._obj = obj

    def scalar_one_or_none(self) -> object:
        return self._obj


class _FakeSession:
    """Returns a fixed project for any select (the resolver only selects one)."""

    def __init__(self, project: object) -> None:
        self._project = project

    async def execute(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult(self._project)


@pytest.fixture(autouse=True)
def _clear_override():
    resolver.set_embedding_override(None)
    yield
    resolver.set_embedding_override(None)


async def test_shared_tier_used_with_override() -> None:
    fake = FakeEmbeddingProvider(dim=GEMINI_SPEC.embedding.dim)
    resolver.set_embedding_override(fake)

    resolved = await resolver.resolve(
        _FakeSession(None), uuid.uuid4(), Capability.embedding, project_id=None
    )
    assert resolved.adapter is fake
    assert resolved.key_source.value == "shared"
    assert resolved.provider_id == GEMINI_SPEC.id
    assert resolved.dim == GEMINI_SPEC.embedding.dim
    assert resolved.model == GEMINI_SPEC.embedding.model


async def test_embedding_pin_match_ok() -> None:
    emb = GEMINI_SPEC.embedding
    project = _FakeProject(provider=GEMINI_SPEC.id, model=emb.model, dim=emb.dim)
    resolver.set_embedding_override(FakeEmbeddingProvider(dim=emb.dim))

    resolved = await resolver.resolve(
        _FakeSession(project), uuid.uuid4(), Capability.embedding, project_id=project.id
    )
    assert resolved.dim == emb.dim


async def test_embedding_pin_mismatch_raises() -> None:
    project = _FakeProject(provider=GEMINI_SPEC.id, model="other-model", dim=1024)
    resolver.set_embedding_override(FakeEmbeddingProvider())

    with pytest.raises(resolver.EmbeddingPinMismatch):
        await resolver.resolve(
            _FakeSession(project), uuid.uuid4(), Capability.embedding, project_id=project.id
        )


async def test_chat_capability_unsupported_in_phase2() -> None:
    with pytest.raises(resolver.UnsupportedCapability):
        await resolver.resolve(_FakeSession(None), uuid.uuid4(), Capability.chat)
