"""Document ingestion endpoints (ARCHITECTURE.md section 6/7).

All handlers are tenant-scoped via the Phase-1 deps: the session already issued
``SET LOCAL app.current_user_id`` and the project is re-verified to belong to the
caller (RLS is the fail-safe). ``owner_id`` is always the authenticated user,
never the request body.

- POST   .../documents            multipart 1..n; stream to disk, guard, dedupe
                                   by (project_id, sha256), create document +
                                   ingest_job rows; 201 [{filename, document_id,
                                   status, dedupe}].
- GET    .../documents            poll: list with status / progress / error_code.
- POST   .../documents/{doc}/reprocess   ready|failed -> queued (delete chunks +
                                          re-enqueue).
- DELETE .../documents/{doc}       cascade chunks + remove the stored file.
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Request, Response, UploadFile, status
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, TenantScopeDep, client_ip
from app.api.errors import api_error
from app.api.schemas import DocumentPublic, UploadResult
from app.core.config import settings
from app.ingestion import storage
from app.ingestion.guards import GuardError, run_guards
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.ingest_job import IngestJob
from app.models.project import Project
from app.services.rate_limit import RateLimiter

router = APIRouter()

# Per-user upload rate limit (backpressure / DoS control, section 14).
_upload_limiter = RateLimiter(max_attempts=60, window_seconds=60.0)

_CHUNK_SIZE = 1024 * 1024


async def _require_project(scope: TenantScopeDep, project_id: uuid.UUID) -> Project:
    project = await scope.get(Project, project_id)
    if project is None:
        raise api_error(404, "not_found", "Project not found.")
    return project


async def _pending_count(scope: TenantScopeDep) -> int:
    result = await scope.session.execute(
        select(func.count())
        .select_from(IngestJob)
        .where(
            IngestJob.owner_id == scope.user_id,
            IngestJob.stage.notin_(("ready", "failed")),
        )
    )
    return int(result.scalar_one())


def _mime_for(upload: UploadFile, kind: str) -> str:
    if upload.content_type:
        return upload.content_type
    return {
        "pdf": "application/pdf",
        "zip": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text": "text/plain",
    }[kind]


@router.post(
    "",
    response_model=list[UploadResult],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    project_id: uuid.UUID,
    request: Request,
    scope: TenantScopeDep,
    user: CurrentUser,
    files: list[UploadFile],
) -> list[UploadResult]:
    """Upload one or more files into a project and enqueue ingestion."""
    project = await _require_project(scope, project_id)

    if not _upload_limiter.allow(f"upload:{user.id}:{client_ip(request)}"):
        raise api_error(429, "rate_limited", "Too many uploads; slow down.")

    results: list[UploadResult] = []
    for upload in files:
        filename = upload.filename or "upload"
        try:
            results.append(await _ingest_one(scope, project, upload, filename))
        except GuardError as exc:
            results.append(
                UploadResult(filename=filename, status=None, dedupe=False, error_code=exc.code)
            )
    return results


async def _ingest_one(
    scope: TenantScopeDep,
    project: Project,
    upload: UploadFile,
    filename: str,
) -> UploadResult:
    """Stream, guard, dedupe, and enqueue a single uploaded file."""
    # Pending-job cap (per user) — 429 when the queue is full.
    if await _pending_count(scope) >= settings.max_pending_ingest_per_user:
        raise api_error(429, "queue_full", "Ingest queue is full; try again later.")

    document_id = uuid.uuid4()
    dest = storage.document_path(document_id)
    max_bytes = settings.max_upload_mb * 1024 * 1024

    async def _reader():
        while True:
            chunk = await upload.read(_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

    size, _head = await storage.write_stream(_reader(), dest=dest, max_bytes=max_bytes)
    data = dest.read_bytes()

    try:
        kind = run_guards(filename, upload.content_type or "", data)
    except GuardError:
        storage.delete_document_file(document_id)
        raise

    sha256 = hashlib.sha256(data).hexdigest()

    # Dedupe by (project_id, sha256). RLS keeps this scoped to the owner.
    existing = await scope.session.execute(
        select(Document).where(Document.project_id == project.id, Document.content_sha256 == sha256)
    )
    dup = existing.scalar_one_or_none()
    if dup is not None:
        storage.delete_document_file(document_id)
        return UploadResult(filename=filename, document_id=dup.id, status=dup.status, dedupe=True)

    document = Document(
        id=document_id,
        project_id=project.id,
        owner_id=scope.user_id,
        filename=filename[:512],
        mime=_mime_for(upload, kind),
        size_bytes=size,
        content_sha256=sha256,
        status=DocumentStatus.queued,
    )
    scope.session.add(document)
    scope.session.add(IngestJob(document_id=document_id, owner_id=scope.user_id, stage="queued"))
    await scope.session.flush()
    return UploadResult(
        filename=filename, document_id=document_id, status=DocumentStatus.queued, dedupe=False
    )


@router.get("", response_model=list[DocumentPublic])
async def list_documents(project_id: uuid.UUID, scope: TenantScopeDep) -> list[DocumentPublic]:
    """List a project's documents (status-poll target)."""
    await _require_project(scope, project_id)
    result = await scope.session.execute(
        select(Document)
        .where(Document.project_id == project_id, Document.owner_id == scope.user_id)
        .order_by(Document.created_at.desc())
    )
    return [DocumentPublic.model_validate(d) for d in result.scalars().all()]


@router.post("/{doc_id}/reprocess", response_model=DocumentPublic)
async def reprocess_document(
    project_id: uuid.UUID, doc_id: uuid.UUID, scope: TenantScopeDep
) -> DocumentPublic:
    """Re-queue a ready|failed document (delete chunks, re-enqueue job)."""
    await _require_project(scope, project_id)
    result = await scope.session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.project_id == project_id,
            Document.owner_id == scope.user_id,
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise api_error(404, "not_found", "Document not found.")
    if document.status not in (DocumentStatus.ready, DocumentStatus.failed):
        raise api_error(409, "invalid_state", "Document is still being processed.")

    from app.ingestion.store import delete_document_chunks

    await delete_document_chunks(scope.session, document_id=doc_id, owner_id=scope.user_id)
    await scope.session.execute(
        update(Document)
        .where(Document.id == doc_id)
        .values(
            status=DocumentStatus.queued,
            error_code=None,
            status_detail=None,
            chunk_count=0,
            embedding_model=None,
            embedding_dim=None,
            page_count=None,
        )
    )
    # Reset an existing job (or create one) to re-run from the start.
    job_result = await scope.session.execute(
        select(IngestJob).where(IngestJob.document_id == doc_id)
    )
    job = job_result.scalar_one_or_none()
    if job is None:
        scope.session.add(IngestJob(document_id=doc_id, owner_id=scope.user_id, stage="queued"))
    else:
        await scope.session.execute(
            update(IngestJob)
            .where(IngestJob.id == job.id)
            .values(
                stage="queued",
                last_cursor=None,
                locked_at=None,
                lease_expires_at=None,
                error=None,
                attempts=0,
            )
        )
    await scope.session.flush()
    refreshed = await scope.session.execute(select(Document).where(Document.id == doc_id))
    return DocumentPublic.model_validate(refreshed.scalar_one())


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    project_id: uuid.UUID, doc_id: uuid.UUID, scope: TenantScopeDep
) -> Response:
    """Delete a document (cascade chunks) and remove the stored file."""
    await _require_project(scope, project_id)
    deleted = await scope.delete(Document, doc_id)
    if not deleted:
        raise api_error(404, "not_found", "Document not found.")
    storage.delete_document_file(doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# The router is mounted under /projects/{project_id}/documents; ``project_id`` is
# a path parameter resolved by FastAPI from the include prefix.
__all__ = ["router"]
