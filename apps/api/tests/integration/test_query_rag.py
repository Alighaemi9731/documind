"""End-to-end RAG query (needs a real RLS-FORCEd Postgres with pgvector).

Seeds a project + documents + chunks via the Phase-2 store with a deterministic
embedder, then exercises the query endpoint through the HTTP layer with a fake
streaming chat provider injected (no GEMINI key, no network). Covers:

- in-doc question -> grounded cited answer (citations all in the retrieved set);
- off-doc question -> REFUSED with NO chat call;
- model GROUNDED:false propagates to grounded=false;
- tenant isolation: A's query never returns/cites B's chunks;
- forged out-of-set citation dropped;
- multilingual fa/en retrieval (incl. a ZWNJ query);
- SSE event order (token* -> citations -> done);
- dropped-stream JSON fallback returns identical citations;
- messages persisted with grounded + a real message_id.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import AsyncIterator, Sequence

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import admin_session, tenant_session
from app.core.text_norm import normalize
from app.ingestion import store
from app.ingestion.chunker import Chunk as ChunkData
from app.main import app
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.enums import DocumentStatus, MessageRole, RegistrationMode
from app.models.message import Message
from app.models.project import Project
from app.models.user import User
from app.providers import resolver
from app.providers.registry import GEMINI_SPEC
from app.security.scoping import TenantScope
from app.services.settings_service import ensure_system_settings
from tests.fakes import FakeChatProvider, RaisingChatProvider

pytestmark = pytest.mark.asyncio

ORIGIN = "https://docs.example.com"
DIM = GEMINI_SPEC.embedding.dim

# Distinct topical chunk texts (normalized form == content here, ASCII/simple).
DOC_TEXTS_EN = [
    "the warranty period for the turbine is five years from delivery",
    "annual maintenance must be performed by a certified technician",
    "the operating temperature range is minus ten to fifty celsius",
]
DOC_TEXT_FA = "مدت گارانتی توربین پنج سال از زمان تحویل است"


class SeparatingEmbedder:
    """Deterministic embedder whose unrelated texts are near-orthogonal.

    Uses SIGNED hash-derived components (in [-1, 1]) so two different texts have
    cosine near 0 while identical texts have cosine 1.0 — giving the grounding
    gate real separation between in-doc and off-doc queries.
    """

    def __init__(self, dim: int = DIM) -> None:
        self._dim = dim

    def _vector(self, text: str) -> list[float]:
        norm_text = normalize(text)
        raw: list[float] = []
        counter = 0
        while len(raw) < self._dim:
            digest = hashlib.sha256(f"{norm_text}|{counter}".encode()).digest()
            for byte in digest:
                raw.append((byte / 255.0) * 2.0 - 1.0)
                if len(raw) >= self._dim:
                    break
            counter += 1
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed_documents(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str, *, model: str) -> list[float]:
        return self._vector(text)

    def dimension(self, model: str) -> int:
        return self._dim


@pytest.fixture(autouse=True)
def _overrides():
    resolver.set_embedding_override(SeparatingEmbedder())
    yield
    resolver.set_embedding_override(None)
    resolver.set_chat_override(None)


@pytest_asyncio.fixture()
async def client(app_db: None) -> AsyncIterator[AsyncClient]:
    async with admin_session() as session:
        row = await ensure_system_settings(session)
        row.registration_mode = RegistrationMode.open
        await session.flush()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=ORIGIN) as c:
        yield c


async def _token(client: AsyncClient, email: str) -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "hunter2hunter2"})
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "hunter2hunter2"}
    )
    return resp.json()["access_token"]


async def _user_id(email: str) -> uuid.UUID:
    async with admin_session() as session:
        row = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
        return row.id


async def _seed_project_with_chunks(
    owner_id: uuid.UUID, texts: list[str]
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a project + one document + chunks (embedded by the fake embedder)."""
    emb = GEMINI_SPEC.embedding
    embedder = SeparatingEmbedder()
    async with tenant_session(owner_id) as session:
        project = Project(
            owner_id=owner_id,
            name="proj",
            embedding_provider=GEMINI_SPEC.id,
            embedding_model=emb.model,
            embedding_dim=emb.dim,
            embedding_normalized=emb.normalized,
        )
        await TenantScope(session, owner_id).add(project)
        project_id = project.id

        document = Document(
            project_id=project_id,
            owner_id=owner_id,
            filename="manual.txt",
            mime="text/plain",
            size_bytes=100,
            content_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            status=DocumentStatus.ready,
        )
        session.add(document)
        await session.flush()

        chunks = [
            ChunkData(
                chunk_index=i,
                content=t,
                normalized_content=normalize(t),
                token_count=10,
                char_start=0,
                char_end=len(t),
                page_no=i + 1,
                section_path=None,
            )
            for i, t in enumerate(texts)
        ]
        vectors = embedder.embed_documents([c.normalized_content for c in chunks], model=emb.model)
        await store.store_chunks(
            session,
            document=document,
            chunks=chunks,
            embeddings=vectors,
            project_id=project_id,
            owner_id=owner_id,
            embedding_dim=emb.dim,
        )
        doc_id = document.id
    return project_id, doc_id


def _parse_sse(body: str) -> list[tuple[str, object]]:
    events: list[tuple[str, object]] = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        if event is not None:
            events.append((event, data))
    return events


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


async def test_in_doc_question_grounded_with_valid_citations(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    owner = await _user_id("owner@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, DOC_TEXTS_EN)

    # The chat model cites the chunk header it was given for the matching topic.
    chat = FakeChatProvider("The warranty is five years [manual.txt p.1 #0].", grounded=True)
    resolver.set_chat_override(chat)

    resp = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": False},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["grounded"] is True
    assert chat.called is True
    assert len(body["citations"]) == 1
    cited_ids = {c["chunk_id"] for c in body["citations"]}
    assert cited_ids.issubset(set(body["used_chunks"]))
    assert "<<<GROUNDED" not in body["answer"]
    assert body["message_id"]


async def test_sse_provider_error_emits_clean_error_frame(client: AsyncClient) -> None:
    token = await _token(client, "errowner@example.com")
    owner = await _user_id("errowner@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, DOC_TEXTS_EN)

    resolver.set_chat_override(RaisingChatProvider())
    resp = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": True},
        headers=h,
    )
    # The stream stays well-formed: a terminal `error` frame, not a truncated body.
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert "error" in [e for e, _ in events]
    err = next(d for e, d in events if e == "error")
    assert err["error"]["code"] == "provider_error"
    # No raw provider/SDK detail (or sentinel) leaks into the stream.
    assert "boom" not in resp.text and "429" not in resp.text
    assert "<<<GROUNDED" not in resp.text


async def test_off_doc_question_refused_without_chat_call(client: AsyncClient) -> None:
    token = await _token(client, "owner2@example.com")
    owner = await _user_id("owner2@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, DOC_TEXTS_EN)

    chat = FakeChatProvider("should never be called", grounded=True)
    resolver.set_chat_override(chat)

    resp = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": "what is the recipe for chocolate cake souffle", "stream": False},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["grounded"] is False
    assert body["citations"] == []
    # The chat provider was NEVER invoked (refused before any LLM call).
    assert chat.called is False
    assert body["message_id"]


async def test_model_grounded_false_propagates(client: AsyncClient) -> None:
    token = await _token(client, "owner3@example.com")
    owner = await _user_id("owner3@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, DOC_TEXTS_EN)

    # Retrieval passes the gate, but the model emits GROUNDED:false -> downgraded.
    chat = FakeChatProvider("I am not fully sure.", grounded=False)
    resolver.set_chat_override(chat)

    resp = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": DOC_TEXTS_EN[1], "stream": False},
        headers=h,
    )
    assert resp.status_code == 200
    assert chat.called is True
    assert resp.json()["grounded"] is False


async def test_forged_citation_dropped(client: AsyncClient) -> None:
    token = await _token(client, "owner4@example.com")
    owner = await _user_id("owner4@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, DOC_TEXTS_EN)

    # The model cites a real header AND a forged one that was never retrieved.
    chat = FakeChatProvider(
        "Answer [manual.txt p.1 #0] and bogus [secret.pdf p.9 #99].", grounded=True
    )
    resolver.set_chat_override(chat)

    resp = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": False},
        headers=h,
    )
    body = resp.json()
    filenames = {c["filename"] for c in body["citations"]}
    assert "secret.pdf" not in filenames
    assert filenames == {"manual.txt"}


async def test_tenant_isolation_query_never_sees_other_tenant(client: AsyncClient) -> None:
    token_a = await _token(client, "a@example.com")
    token_b = await _token(client, "b@example.com")
    a = await _user_id("a@example.com")
    b = await _user_id("b@example.com")
    project_a, _ = await _seed_project_with_chunks(a, DOC_TEXTS_EN)
    project_b, _ = await _seed_project_with_chunks(b, ["totally different content about gardening"])

    # B tries to query A's project -> 404 (not owned).
    resp = await client.post(
        f"/api/projects/{project_a}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": False},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404

    # B querying its OWN project never returns or cites A's chunks.
    chat = FakeChatProvider("answer", grounded=True)
    resolver.set_chat_override(chat)
    resp_b = await client.post(
        f"/api/projects/{project_b}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": False},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    body = resp_b.json()
    # B's query never returns or cites any of A's chunk ids (cross-tenant leak).
    a_chunk_ids = {str(cid) for cid in await _chunk_ids_of(a)}
    cited = {c["chunk_id"] for c in body["citations"]}
    used = set(body.get("used_chunks", []))
    assert cited.isdisjoint(a_chunk_ids)
    assert used.isdisjoint(a_chunk_ids)


async def _chunk_ids_of(owner_id: uuid.UUID) -> list[uuid.UUID]:
    async with tenant_session(owner_id) as session:
        rows = (await session.execute(select(Chunk.id))).scalars().all()
        return list(rows)


async def test_persian_zwnj_query_retrieves(client: AsyncClient) -> None:
    token = await _token(client, "fa@example.com")
    owner = await _user_id("fa@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, [DOC_TEXT_FA] + DOC_TEXTS_EN)

    chat = FakeChatProvider("پاسخ [manual.txt p.1 #0]", grounded=True)
    resolver.set_chat_override(chat)

    # Same question with a ZWNJ + Arabic-variant Yeh/Kaf inserted; text_norm
    # folds them so the normalized query still matches the stored chunk.
    zwnj_question = "مدت گارانتی‌ توربين پنج سال از زمان تحويل است"
    assert "‌" in zwnj_question  # contains a ZWNJ
    resp = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": zwnj_question, "stream": False},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["grounded"] is True
    assert chat.called is True


async def test_sse_event_order_and_no_sentinel(client: AsyncClient) -> None:
    token = await _token(client, "sse@example.com")
    owner = await _user_id("sse@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, DOC_TEXTS_EN)

    chat = FakeChatProvider("Five years [manual.txt p.1 #0].", grounded=True, chunk_size=2)
    resolver.set_chat_override(chat)

    resp = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": True},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    names = [e for e, _ in events]
    # token* then citations then done, in that order.
    assert names[-1] == "done"
    assert names[-2] == "citations"
    assert all(n == "token" for n in names[:-2])
    # The literal sentinel never reaches the client.
    answer = "".join(d["text"] for n, d in events if n == "token")
    assert "<<<GROUNDED" not in answer
    done = events[-1][1]
    assert done["grounded"] is True
    assert done["message_id"]


async def test_json_fallback_matches_stream_citations(client: AsyncClient) -> None:
    token = await _token(client, "fb@example.com")
    owner = await _user_id("fb@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, DOC_TEXTS_EN)

    answer_text = "Five years [manual.txt p.1 #0]."
    resolver.set_chat_override(FakeChatProvider(answer_text, grounded=True, chunk_size=4))
    stream = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": True},
        headers=h,
    )
    stream_events = _parse_sse(stream.text)
    stream_citations = next(d for n, d in stream_events if n == "citations")

    resolver.set_chat_override(FakeChatProvider(answer_text, grounded=True, chunk_size=4))
    js = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": False},
        headers=h,
    )
    json_citations = js.json()["citations"]

    # Retrieval is idempotent -> identical citation chunk-id sets.
    assert {c["chunk_id"] for c in stream_citations} == {c["chunk_id"] for c in json_citations}


async def test_messages_persisted_with_grounded_and_id(client: AsyncClient) -> None:
    token = await _token(client, "persist@example.com")
    owner = await _user_id("persist@example.com")
    h = {"Authorization": f"Bearer {token}"}
    project_id, _doc = await _seed_project_with_chunks(owner, DOC_TEXTS_EN)

    resolver.set_chat_override(
        FakeChatProvider("Five years [manual.txt p.1 #0].", grounded=True)
    )
    resp = await client.post(
        f"/api/projects/{project_id}/query",
        json={"question": DOC_TEXTS_EN[0], "stream": False},
        headers=h,
    )
    message_id = resp.json()["message_id"]

    async with tenant_session(owner) as session:
        msgs = (
            (await session.execute(select(Message).order_by(Message.created_at)))
            .scalars()
            .all()
        )
        roles = [m.role for m in msgs]
        assert MessageRole.user in roles
        assert MessageRole.assistant in roles
        assistant = next(m for m in msgs if m.role is MessageRole.assistant)
        assert str(assistant.id) == message_id
        assert assistant.grounded is True
        assert assistant.citations  # persisted validated citations

        # A conversation row exists and owns the messages.
        convs = (await session.execute(select(Conversation))).scalars().all()
        assert len(convs) == 1
        assert all(m.conversation_id == convs[0].id for m in msgs)
