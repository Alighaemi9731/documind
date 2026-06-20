"""End-to-end ingestion integration tests (need a real RLS-FORCEd Postgres).

Covers: process_one -> chunks stored with halfvec(768) + stamped
owner/project/dim + generated tsvector populated; dim-mismatch reject; ingest-job
state machine + lease re-claim; worker sets GUC from job.owner_id; tenant
isolation on documents/chunks (RLS, no admin bypass).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.core.db import admin_session, tenant_session, worker_tenant_session
from app.ingestion import store, worker
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentErrorCode, DocumentStatus
from app.models.ingest_job import IngestJob
from app.models.project import Project
from app.models.user import User
from app.providers import resolver
from app.providers.registry import GEMINI_SPEC
from app.security.scoping import TenantScope
from tests.fakes import (
    FakeEmbeddingProvider,
    RaisingEmbeddingProvider,
    TransientEmbeddingProvider,
    WrongDimEmbeddingProvider,
)

pytestmark = pytest.mark.asyncio

DIM = GEMINI_SPEC.embedding.dim
TEXT_BODY = ("سلام دنیا. این یک سند آزمایشی است.\n" + "hello world test document. ") * 40


@pytest.fixture(autouse=True)
def _clear_override():
    resolver.set_embedding_override(None)
    yield
    resolver.set_embedding_override(None)


async def _make_user() -> uuid.UUID:
    uid = uuid.uuid4()
    async with admin_session() as session:
        session.add(User(id=uid, email=f"{uid}@example.com"))
        await session.flush()
    return uid


async def _make_project(owner_id: uuid.UUID) -> uuid.UUID:
    emb = GEMINI_SPEC.embedding
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
        return project.id


async def _make_document(owner_id: uuid.UUID, project_id: uuid.UUID) -> uuid.UUID:
    doc_id = uuid.uuid4()
    async with worker_tenant_session(owner_id) as session:
        session.add(
            Document(
                id=doc_id,
                project_id=project_id,
                owner_id=owner_id,
                filename="doc.txt",
                mime="text/plain",
                size_bytes=len(TEXT_BODY.encode()),
                content_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                status=DocumentStatus.queued,
            )
        )
        session.add(IngestJob(document_id=doc_id, owner_id=owner_id, stage="queued"))
        await session.flush()
    return doc_id


def _reader(body: bytes):
    async def read(_doc_id: uuid.UUID) -> bytes:
        return body

    return read


async def test_process_one_stores_embedded_chunks(app_db: None) -> None:
    owner = await _make_user()
    project_id = await _make_project(owner)
    doc_id = await _make_document(owner, project_id)

    resolver.set_embedding_override(FakeEmbeddingProvider(dim=DIM))
    status = await worker.process_one(None, read_bytes=_reader(TEXT_BODY.encode()))
    assert status is DocumentStatus.ready

    async with worker_tenant_session(owner) as session:
        doc = (await session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert doc.status is DocumentStatus.ready
        assert doc.chunk_count > 0
        assert doc.embedding_dim == DIM
        assert doc.embedding_model == GEMINI_SPEC.embedding.model

        chunks = (
            (await session.execute(select(Chunk).where(Chunk.document_id == doc_id)))
            .scalars()
            .all()
        )
        assert len(chunks) == doc.chunk_count
        for c in chunks:
            assert c.owner_id == owner  # stamped
            assert c.project_id == project_id  # stamped
            assert c.embedding_dim == DIM  # stamped
            assert len(c.embedding.to_list()) == DIM  # pgvector HalfVector

        # The generated tsvector is populated (keyword leg works).
        tsv_count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM chunks "
                    "WHERE document_id = :d AND content_tsv IS NOT NULL "
                    "AND content_tsv <> ''::tsvector"
                ),
                {"d": doc_id},
            )
        ).scalar_one()
        assert tsv_count == len(chunks)


async def test_dim_mismatch_rejected(app_db: None) -> None:
    owner = await _make_user()
    project_id = await _make_project(owner)
    await _make_document(owner, project_id)

    resolver.set_embedding_override(WrongDimEmbeddingProvider(dim=DIM))
    status = await worker.process_one(None, read_bytes=_reader(TEXT_BODY.encode()))
    # The store rejects the wrong-dim vector => the document fails (EMBED_ERROR).
    assert status is DocumentStatus.failed

    async with worker_tenant_session(owner) as session:
        docs = (await session.execute(select(Document))).scalars().all()
        assert docs[0].status is DocumentStatus.failed
        # No chunks were written (transaction rolled back the insert).
        chunks = (await session.execute(select(Chunk))).scalars().all()
        assert chunks == []


async def test_poison_job_is_marked_failed(app_db: None) -> None:
    owner = await _make_user()
    project_id = await _make_project(owner)
    doc_id = await _make_document(owner, project_id)

    bad = RaisingEmbeddingProvider(dim=DIM)
    resolver.set_embedding_override(bad)
    status = await worker.process_one(None, read_bytes=_reader(TEXT_BODY.encode()))
    # An unexpected embedder error fails the document instead of hanging it.
    assert status is DocumentStatus.failed

    async with worker_tenant_session(owner) as session:
        doc = (await session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert doc.status is DocumentStatus.failed
        assert doc.error_code is DocumentErrorCode.EMBED_ERROR

    # The job is terminal -> never re-claimed (no infinite retry).
    from app.core.db import get_sessionmaker

    maker = get_sessionmaker()
    async with maker() as s, s.begin():
        assert await worker.claim_job(s) is None


async def test_transient_embed_does_not_fail(app_db: None) -> None:
    owner = await _make_user()
    project_id = await _make_project(owner)
    doc_id = await _make_document(owner, project_id)

    transient = TransientEmbeddingProvider(dim=DIM)
    resolver.set_embedding_override(transient)
    status = await worker.process_one(None, read_bytes=_reader(TEXT_BODY.encode()))
    # A rate limit is transient: the doc is NOT failed; it is retried later.
    assert status is DocumentStatus.embedding

    async with worker_tenant_session(owner) as session:
        doc = (await session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert doc.status is not DocumentStatus.failed
        job = (
            await session.execute(select(IngestJob).where(IngestJob.document_id == doc_id))
        ).scalar_one()
        assert job.stage != "failed"


async def test_state_machine_terminal_and_lease_reclaim(app_db: None) -> None:
    owner = await _make_user()
    project_id = await _make_project(owner)
    doc_id = await _make_document(owner, project_id)

    # A job whose lease has NOT expired is not claimable by a second worker.
    from app.core.db import get_sessionmaker

    maker = get_sessionmaker()
    async with maker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(owner)}
        )
        job = (
            await session.execute(select(IngestJob).where(IngestJob.document_id == doc_id))
        ).scalar_one()
        # Simulate an in-flight lease held by another worker.
        future = datetime.now(UTC) + timedelta(seconds=300)
        job.locked_at = datetime.now(UTC)
        job.lease_expires_at = future
        await session.flush()

    async with maker() as session, session.begin():
        claimed = await worker.claim_job(session)
    assert claimed is None  # leased, not yet expired

    # Expire the lease => the job becomes re-claimable.
    async with maker() as session, session.begin():
        await session.execute(
            text("UPDATE ingest_jobs SET lease_expires_at = :past WHERE document_id = :d"),
            {"past": datetime.now(UTC) - timedelta(seconds=1), "d": doc_id},
        )

    async with maker() as session, session.begin():
        reclaimed = await worker.claim_job(session)
    assert reclaimed is not None
    assert reclaimed.document_id == doc_id

    # A terminal (ready) job is never claimed.
    async with maker() as session, session.begin():
        await session.execute(
            text(
                "UPDATE ingest_jobs SET stage='ready', lease_expires_at=NULL WHERE document_id=:d"
            ),
            {"d": doc_id},
        )
    async with maker() as session, session.begin():
        assert await worker.claim_job(session) is None


async def test_tenant_isolation_documents_and_chunks(app_db: None) -> None:
    a = await _make_user()
    b = await _make_user()
    project_a = await _make_project(a)
    await _make_document(a, project_a)

    resolver.set_embedding_override(FakeEmbeddingProvider(dim=DIM))
    await worker.process_one(None, read_bytes=_reader(TEXT_BODY.encode()))

    # B, scoped to itself, sees NONE of A's documents or chunks (RLS, no bypass).
    async with worker_tenant_session(b) as session:
        b_docs = (await session.execute(select(Document))).scalars().all()
        b_chunks = (await session.execute(select(Chunk))).scalars().all()
    assert b_docs == []
    assert b_chunks == []

    # A sees its own rows.
    async with worker_tenant_session(a) as session:
        a_docs = (await session.execute(select(Document))).scalars().all()
        a_chunks = (await session.execute(select(Chunk))).scalars().all()
    assert len(a_docs) == 1
    assert len(a_chunks) > 0


async def test_worker_sets_guc_from_job_owner(app_db: None) -> None:
    owner = await _make_user()
    project_id = await _make_project(owner)
    await _make_document(owner, project_id)

    captured: dict[str, str | None] = {}
    fake = FakeEmbeddingProvider(dim=DIM)

    # Wrap the store to capture the GUC seen during the tenant-scoped insert.
    original = store.store_chunks

    async def _spy(session, **kwargs):  # noqa: ANN001
        result = await session.execute(text("SELECT current_setting('app.current_user_id', true)"))
        captured["guc"] = result.scalar()
        return await original(session, **kwargs)

    store.store_chunks = _spy  # type: ignore[assignment]
    worker.store.store_chunks = _spy  # type: ignore[assignment]
    try:
        resolver.set_embedding_override(fake)
        await worker.process_one(None, read_bytes=_reader(TEXT_BODY.encode()))
    finally:
        store.store_chunks = original  # type: ignore[assignment]
        worker.store.store_chunks = original  # type: ignore[assignment]

    assert captured.get("guc") == str(owner)


async def test_no_runnable_job_returns_none(app_db: None) -> None:
    result = await worker.process_one(None, read_bytes=_reader(b"x"))
    assert result is None
