"""Re-embed orchestration (ADR-0015). Ingestion drives; data-model owns schema.

When a user changes a project's embedding provider/model to a DIFFERENT dim, the
in-place switch is blocked (409 at the settings layer) and the only path forward
is an explicit re-embed job: per project, re-pin the embedding identity, then
re-queue every document so the existing worker re-runs parse -> chunk -> embed ->
store with the new embedding. The store already does delete-then-insert keyed by
``document_id`` (re-stamping owner/project/new-dim) and builds the per-dim partial
HNSW index lazily on first ingest, so this module stays a thin orchestrator.

Scope note (minimal correct implementation): this re-pins the project and resets
the documents + ingest_jobs to ``queued`` under the owning tenant's RLS scope.
The heavy lifting (parse/chunk/embed/store + the new partial HNSW) is the
worker's existing path — no schema change here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import assert_guc
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.ingest_job import IngestJob
from app.models.project import Project
from app.providers import registry


class ReembedError(RuntimeError):
    """A re-embed request that cannot be satisfied (bad provider/model)."""


async def requeue_project_reembed(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    project_id: uuid.UUID,
    provider: str,
    model: str,
) -> int:
    """Re-pin ``project`` to ``(provider, model, dim)`` and re-queue its documents.

    Returns the number of documents re-queued. Must run inside a tenant session
    scoped to ``owner_id`` (RLS owner-only). The new dim is read from the
    ProviderSpec — never client-supplied.
    """
    await assert_guc(session, owner_id)

    try:
        spec = registry.get_spec(provider)
    except KeyError as exc:
        raise ReembedError(f"Unknown provider {provider!r}.") from exc
    if spec.embedding is None or model != spec.embedding.model:
        raise ReembedError("Provider/model does not offer this embedding identity.")
    new_dim = spec.embedding.dim
    normalized = spec.embedding.normalized

    proj_result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
    )
    project = proj_result.scalar_one_or_none()
    if project is None:
        raise ReembedError("Project not found for re-embed.")

    # Re-pin the project embedding identity (the only sanctioned dim change).
    project.embedding_provider = provider
    project.embedding_model = model
    project.embedding_dim = new_dim
    project.embedding_normalized = normalized
    await session.flush()

    # Re-queue every document: reset status + (re)create a queued ingest_job. The
    # worker re-runs the pipeline and the store delete-then-inserts the chunks
    # with the new embedding/dim.
    doc_result = await session.execute(
        select(Document.id).where(Document.project_id == project_id, Document.owner_id == owner_id)
    )
    doc_ids = [row[0] for row in doc_result.all()]

    for doc_id in doc_ids:
        await session.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status=DocumentStatus.queued, error_code=None, status_detail=None)
        )
        await _reset_or_create_job(session, document_id=doc_id, owner_id=owner_id)

    await session.flush()
    return len(doc_ids)


async def _reset_or_create_job(
    session: AsyncSession, *, document_id: uuid.UUID, owner_id: uuid.UUID
) -> None:
    """Reset an existing ingest_job back to queued, or create a fresh one."""
    result = await session.execute(select(IngestJob).where(IngestJob.document_id == document_id))
    job = result.scalar_one_or_none()
    if job is None:
        session.add(
            IngestJob(document_id=document_id, owner_id=owner_id, stage="queued", attempts=0)
        )
        return
    await session.execute(
        update(IngestJob)
        .where(IngestJob.id == job.id)
        .values(stage="queued", attempts=0, locked_at=None, lease_expires_at=None, error=None)
    )


__all__ = ["ReembedError", "requeue_project_reembed"]
