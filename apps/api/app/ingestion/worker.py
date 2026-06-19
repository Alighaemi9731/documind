"""In-process asyncio ingest worker (ADR-0005).

Claims an ``ingest_jobs`` row with ``SELECT ... FOR UPDATE SKIP LOCKED`` plus a
lease (``locked_at`` / ``lease_expires_at``); a crashed worker's lease expires
and the job is re-claimable. It runs the stages parse -> chunk -> embed -> store,
advancing ``documents.status`` (queued -> parsing -> chunking -> embedding ->
ready) and, on failure, recording a typed :class:`DocumentErrorCode`.

A rate-limited embed is TRANSIENT: the document stays ``embedding`` and the job
keeps its lease/``last_cursor`` rather than failing (resumable). The worker sets
the tenant GUC from ``job.owner_id`` via ``worker_tenant_session`` (ADR-0002), so
RLS scopes all of its reads/writes to the owning tenant.

:func:`process_one` is synchronous-friendly for tests (drives exactly one job to
completion with an injected embedder). :func:`run_forever` is the production loop
bounded by ``INGEST_CONCURRENCY``; it is started in app lifespan only when
``ENVIRONMENT != 'test'``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.db import get_sessionmaker, worker_tenant_session
from app.ingestion import store
from app.ingestion.chunker import chunk_segments
from app.ingestion.guards import GuardError
from app.ingestion.parsers import Segment
from app.ingestion.parsers.docx import parse_docx
from app.ingestion.parsers.pdf import parse_pdf
from app.ingestion.parsers.text import parse_text
from app.models.document import Document
from app.models.enums import Capability, DocumentErrorCode, DocumentStatus
from app.models.ingest_job import IngestJob
from app.models.project import Project
from app.providers import resolver
from app.providers.errors import ProviderTransientError
from app.providers.interfaces import EmbeddingProvider

logger = logging.getLogger("documind.ingest")

# How long a claimed job is leased before it becomes re-claimable.
LEASE_SECONDS = 300
EMBED_BATCH = 64
# A job claimed this many times without reaching a terminal state (e.g. the
# worker keeps crashing mid-job) is reaped and marked failed.
MAX_ATTEMPTS = 5

# A pluggable reader for the uploaded bytes (temp-file path is stored elsewhere
# in production; tests inject an in-memory reader).
BytesReader = Callable[[uuid.UUID], Awaitable[bytes]]


class TransientEmbedError(Exception):
    """A retryable embed failure (e.g. rate limit). Does NOT fail the document."""


def _now() -> datetime:
    return datetime.now(UTC)


async def claim_job(session: AsyncSession) -> IngestJob | None:
    """Claim the next runnable job with FOR UPDATE SKIP LOCKED + lease.

    Runnable = stage not terminal AND (never leased OR lease expired). Sets a
    fresh lease on the claimed row. Must run inside a transaction.
    """
    now = _now()
    result = await session.execute(
        text(
            """
            SELECT id FROM ingest_jobs
            WHERE stage NOT IN ('ready', 'failed')
              AND attempts < :max_attempts
              AND (lease_expires_at IS NULL OR lease_expires_at < :now)
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        ),
        {"now": now, "max_attempts": MAX_ATTEMPTS},
    )
    row = result.first()
    if row is None:
        return None
    job_id = row[0]
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    await session.execute(
        update(IngestJob)
        .where(IngestJob.id == job_id)
        .values(locked_at=now, lease_expires_at=lease_until, attempts=IngestJob.attempts + 1)
    )
    fetched = await session.execute(select(IngestJob).where(IngestJob.id == job_id))
    return fetched.scalar_one()


def _parse(kind: str, data: bytes) -> list[Segment]:
    if kind == "pdf":
        return parse_pdf(data)
    if kind == "zip":  # docx
        return parse_docx(data)
    return parse_text(data)


async def _set_status(
    session: AsyncSession,
    document_id: uuid.UUID,
    status: DocumentStatus,
    *,
    error_code: DocumentErrorCode | None = None,
    detail: str | None = None,
) -> None:
    await session.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(status=status, error_code=error_code, status_detail=detail)
    )


async def process_job(
    session: AsyncSession,
    job: IngestJob,
    *,
    embedder: EmbeddingProvider,
    read_bytes: BytesReader,
    kind: str | None = None,
) -> DocumentStatus:
    """Run one job to a terminal/transient outcome within ``session``.

    Returns the resulting document status. Raises nothing for typed guard
    failures (records them as ``failed`` + error_code); a transient embed keeps
    the document in ``embedding`` and re-raises :class:`TransientEmbedError` so
    the caller leaves the lease/cursor for a later resume.
    """
    doc_result = await session.execute(select(Document).where(Document.id == job.document_id))
    document = doc_result.scalar_one()
    proj_result = await session.execute(select(Project).where(Project.id == document.project_id))
    project = proj_result.scalar_one()
    detected_kind = kind or _kind_from_mime(document.mime)
    stage_code = DocumentErrorCode.PARSE_ERROR

    try:
        # ---- parse -------------------------------------------------------- #
        await _set_status(session, document.id, DocumentStatus.parsing)
        data = await read_bytes(document.id)
        segments = _parse(detected_kind, data)
        await session.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(page_count=_page_count(segments))
        )

        # ---- chunk -------------------------------------------------------- #
        await _set_status(session, document.id, DocumentStatus.chunking)
        chunks = chunk_segments(segments)
        if not chunks:
            raise GuardError(DocumentErrorCode.NO_TEXT, "No chunks produced from the document.")

        # ---- embed -------------------------------------------------------- #
        stage_code = DocumentErrorCode.EMBED_ERROR
        await _set_status(session, document.id, DocumentStatus.embedding)
        resolved = await resolver.resolve(
            session, job.owner_id, Capability.embedding, project_id=project.id
        )
        try:
            vectors = _embed_all(embedder, [c.normalized_content for c in chunks], resolved.model)
        except ProviderTransientError as exc:
            # Rate limit / quota / 5xx: do NOT fail. The claim lease provides the
            # backoff; the job is re-claimed and re-embedded after it expires.
            logger.warning("transient embed error (doc %s): %s", document.id, exc)
            raise TransientEmbedError(str(exc)) from exc

        # ---- store -------------------------------------------------------- #
        await store.delete_document_chunks(session, document_id=document.id, owner_id=job.owner_id)
        await store.store_chunks(
            session,
            document=document,
            chunks=chunks,
            embeddings=vectors,
            project_id=project.id,
            owner_id=job.owner_id,
            embedding_dim=resolved.dim,
        )
        await session.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(embedding_model=resolved.model)
        )
        await _set_status(session, document.id, DocumentStatus.ready)
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job.id)
            .values(stage="ready", lease_expires_at=None, locked_at=None, error=None)
        )
        return DocumentStatus.ready

    except GuardError as exc:
        await _set_status(
            session, document.id, DocumentStatus.failed, error_code=exc.code, detail=exc.message
        )
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job.id)
            .values(stage="failed", error=exc.message)
        )
        return DocumentStatus.failed
    except store.DimensionMismatch as exc:
        await _set_status(
            session,
            document.id,
            DocumentStatus.failed,
            error_code=DocumentErrorCode.EMBED_ERROR,
            detail=str(exc),
        )
        await session.execute(
            update(IngestJob).where(IngestJob.id == job.id).values(stage="failed", error=str(exc))
        )
        return DocumentStatus.failed
    except TransientEmbedError:
        raise  # handled by the caller (document stays non-failed; retried later)
    except Exception as exc:  # noqa: BLE001 - any other failure terminates the job
        # Poison job / non-transient provider error / unexpected: fail it (with a
        # stage-appropriate code) so it never re-claims forever or hangs a doc.
        await _set_status(
            session,
            document.id,
            DocumentStatus.failed,
            error_code=stage_code,
            detail=str(exc)[:500],
        )
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job.id)
            .values(stage="failed", error=str(exc)[:500])
        )
        logger.exception("ingest job %s failed", job.id)
        return DocumentStatus.failed


def _embed_all(embedder: EmbeddingProvider, texts: list[str], model: str) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        out.extend(embedder.embed_documents(batch, model=model))
    return out


def _page_count(segments: list[Segment]) -> int | None:
    pages = {s.page_no for s in segments if s.page_no is not None}
    return len(pages) if pages else None


def _kind_from_mime(mime: str) -> str:
    base = mime.split(";")[0].strip().lower()
    if base == "application/pdf":
        return "pdf"
    if base == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return "zip"
    return "text"


async def reap_exhausted_jobs(maker: async_sessionmaker[AsyncSession]) -> None:
    """Fail jobs that exhausted ``MAX_ATTEMPTS`` without reaching a terminal state.

    Covers the rare case where the worker repeatedly crashes mid-job (each crash
    re-claims and bumps ``attempts``). Without this the document would hang
    non-terminal forever once ``claim_job`` stops re-claiming it.
    """
    now = _now()
    async with maker() as queue_session, queue_session.begin():
        rows = (
            await queue_session.execute(
                text(
                    "SELECT id, document_id, owner_id FROM ingest_jobs "
                    "WHERE stage NOT IN ('ready','failed') AND attempts >= :max "
                    "AND (lease_expires_at IS NULL OR lease_expires_at < :now)"
                ),
                {"max": MAX_ATTEMPTS, "now": now},
            )
        ).all()
        for row in rows:
            await queue_session.execute(
                update(IngestJob)
                .where(IngestJob.id == row.id)
                .values(stage="failed", error="max attempts exceeded")
            )
    # Mark each affected document failed under its own tenant scope (RLS).
    for row in rows:
        async with worker_tenant_session(row.owner_id) as session:
            await _set_status(
                session,
                row.document_id,
                DocumentStatus.failed,
                error_code=DocumentErrorCode.EMBED_ERROR,
                detail="Processing failed after repeated attempts.",
            )


async def process_one(
    session_factory: async_sessionmaker[AsyncSession] | None,
    embedder: EmbeddingProvider,
    *,
    read_bytes: BytesReader,
) -> DocumentStatus | None:
    """Claim + process exactly one job (test entry point).

    Claims under a short transaction, then processes inside a tenant session
    scoped to the job's ``owner_id``. Returns the resulting status, or ``None``
    if there was no runnable job.
    """
    maker = session_factory or get_sessionmaker()
    await reap_exhausted_jobs(maker)

    # Claim under a brief transaction. The claim is intentionally NOT tenant-
    # scoped: ingest_jobs is non-RLS queue metadata scanned across owners; the
    # process step below is tenant-scoped via worker_tenant_session.
    async with maker() as claim_session, claim_session.begin():
        job = await claim_job(claim_session)
        if job is None:
            return None
        owner_id = job.owner_id
        job_id = job.id

    async with worker_tenant_session(owner_id) as session:
        fetched = await session.execute(select(IngestJob).where(IngestJob.id == job_id))
        job = fetched.scalar_one()
        try:
            return await process_job(session, job, embedder=embedder, read_bytes=read_bytes)
        except TransientEmbedError:
            return DocumentStatus.embedding


async def run_forever(
    embedder: EmbeddingProvider,
    *,
    read_bytes: BytesReader,
    poll_interval: float = 2.0,
) -> None:
    """Bounded polling loop (production). Concurrency = ``INGEST_CONCURRENCY``."""
    semaphore = asyncio.Semaphore(max(1, settings.ingest_concurrency))

    async def _drain() -> None:
        async with semaphore:
            try:
                await process_one(None, embedder, read_bytes=read_bytes)
            except Exception:  # noqa: BLE001 - never let the loop die
                logger.exception("ingest worker iteration failed")

    while True:
        await _drain()
        await asyncio.sleep(poll_interval)


__all__ = [
    "claim_job",
    "process_job",
    "process_one",
    "reap_exhausted_jobs",
    "run_forever",
    "TransientEmbedError",
    "LEASE_SECONDS",
    "MAX_ATTEMPTS",
]
