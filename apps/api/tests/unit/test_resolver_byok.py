"""Resolver BYOK-vs-shared precedence, per-capability independence, and
key_source attribution (ADR-0006). Uses a query-aware fake session + override
hooks so no operator key / network / DB is needed."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import Capability, KeySource
from app.providers import resolver
from app.providers.registry import GEMINI_SPEC, OPENAI_SPEC
from tests.fakes import FakeChatProvider, FakeEmbeddingProvider

pytestmark = pytest.mark.asyncio


class _Row:
    """Generic attribute bag standing in for a selection/credential/project row."""

    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class _Result:
    def __init__(self, obj: object) -> None:
        self._obj = obj

    def scalar_one_or_none(self) -> object:
        return self._obj


class _Session:
    """Routes selects by table name to the configured rows.

    ``selections`` maps capability -> (provider, model); ``credentials`` is the
    set of providers with an active BYOK key; ``project`` is the pinned project.
    """

    def __init__(
        self,
        *,
        selections: dict[Capability, tuple[str, str]] | None = None,
        credentials: set[str] | None = None,
        project: object | None = None,
    ) -> None:
        self._selections = selections or {}
        self._credentials = credentials or set()
        self._project = project

    async def execute(self, statement, *_a, **_k) -> _Result:  # noqa: ANN001
        sql = str(statement).lower()
        if "provider_selections" in sql:
            # The statement binds the capability value; match whichever selection
            # is configured (the resolver only queries one capability at a time).
            params = _bind_values(statement)
            cap_value = params.get("capability_1")
            for cap, (provider, model) in self._selections.items():
                if cap.value == cap_value:
                    return _Result(_Row(provider=provider, model=model, capability=cap.value))
            return _Result(None)
        if "provider_keys" in sql:
            params = _bind_values(statement)
            provider = params.get("provider_1")
            if provider in self._credentials:
                return _Result(_Row(provider=provider, ciphertext=b"x", is_active=True))
            return _Result(None)
        if "projects" in sql:
            return _Result(self._project)
        return _Result(None)


def _bind_values(statement) -> dict:  # noqa: ANN001
    try:
        return dict(statement.compile().params)
    except Exception:  # noqa: BLE001
        return {}


@pytest.fixture(autouse=True)
def _override_and_keystore(monkeypatch: pytest.MonkeyPatch):
    fake_emb = FakeEmbeddingProvider(dim=OPENAI_SPEC.embedding.dim)
    fake_chat = FakeChatProvider("hi")
    resolver.set_embedding_override(fake_emb)
    resolver.set_chat_override(fake_chat)

    # load_user_key is bypassed by the override hooks, but guard against a real
    # decrypt by returning a dummy Secret.
    async def _fake_load(session, *, user_id, provider):  # noqa: ANN001, ANN202
        from app.core.security import Secret

        return Secret("dummy")

    monkeypatch.setattr(resolver.keystore, "load_user_key", _fake_load)
    yield fake_emb, fake_chat
    resolver.set_embedding_override(None)
    resolver.set_chat_override(None)


async def test_byok_chat_takes_precedence_over_shared() -> None:
    session = _Session(
        selections={Capability.chat: (OPENAI_SPEC.id, "gpt-4o-mini")},
        credentials={OPENAI_SPEC.id},
    )
    resolved = await resolver.resolve_chat(session, uuid.uuid4())
    assert resolved.key_source is KeySource.byok
    assert resolved.provider_id == OPENAI_SPEC.id
    assert resolved.model == "gpt-4o-mini"


async def test_chat_falls_back_to_shared_without_credential() -> None:
    # Selection exists but NO active BYOK key -> shared operator default.
    session = _Session(
        selections={Capability.chat: (OPENAI_SPEC.id, "gpt-4o-mini")},
        credentials=set(),
    )
    resolved = await resolver.resolve_chat(session, uuid.uuid4())
    assert resolved.key_source is KeySource.shared
    assert resolved.provider_id == GEMINI_SPEC.id


async def test_no_selection_uses_shared() -> None:
    session = _Session(selections={}, credentials={OPENAI_SPEC.id})
    resolved = await resolver.resolve_chat(session, uuid.uuid4())
    assert resolved.key_source is KeySource.shared


async def test_per_capability_independence() -> None:
    """BYOK chat (OpenAI) coexists with SHARED embeddings (Gemini)."""
    project = _Row(
        id=uuid.uuid4(),
        embedding_provider=GEMINI_SPEC.id,
        embedding_model=GEMINI_SPEC.embedding.model,
        embedding_dim=GEMINI_SPEC.embedding.dim,
    )
    session = _Session(
        selections={Capability.chat: (OPENAI_SPEC.id, "gpt-4o-mini")},
        credentials={OPENAI_SPEC.id},
        project=project,
    )
    uid = uuid.uuid4()

    chat = await resolver.resolve_chat(session, uid)
    assert chat.key_source is KeySource.byok and chat.provider_id == OPENAI_SPEC.id

    emb = await resolver.resolve(session, uid, Capability.embedding, project_id=project.id)
    # No embedding selection/credential -> shared Gemini, independent of chat.
    assert emb.key_source is KeySource.shared
    assert emb.provider_id == GEMINI_SPEC.id


async def test_byok_embedding_pin_mismatch_raises() -> None:
    # BYOK embedding selection=OpenAI(1536) but project pinned to Gemini(768).
    project = _Row(
        id=uuid.uuid4(),
        embedding_provider=GEMINI_SPEC.id,
        embedding_model=GEMINI_SPEC.embedding.model,
        embedding_dim=GEMINI_SPEC.embedding.dim,
    )
    session = _Session(
        selections={Capability.embedding: (OPENAI_SPEC.id, OPENAI_SPEC.embedding.model)},
        credentials={OPENAI_SPEC.id},
        project=project,
    )
    with pytest.raises(resolver.EmbeddingPinMismatch):
        await resolver.resolve(session, uuid.uuid4(), Capability.embedding, project_id=project.id)
