"""RAG query endpoint (ARCHITECTURE.md section 6/8, ADR-0008).

``POST /api/projects/{project_id}/query`` — Bearer + tenant-scoped. Body
``{question, stream?=true, conversation_id?}``. Owner comes from the JWT, project
from the path; the project is re-verified to belong to the caller (RLS is the
fail-safe). The FULL retrieved set is captured BEFORE streaming, and no tenant DB
read happens mid-stream (section 8).

- ``stream=true`` -> ``text/event-stream`` (token* -> citations -> done), behind
  Caddy ``flush_interval -1``.
- ``stream=false`` -> JSON ``{answer, citations, grounded, used_chunks, provider,
  message_id}`` with identical content (retrieval is idempotent).

The whole request runs inside ONE tenant transaction opened explicitly here (not
via the request-scoped dependency) so the transaction spans the entire stream and
commits the persisted messages when the stream completes.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, client_ip
from app.api.errors import api_error
from app.api.schemas import QueryRequest
from app.core.db import tenant_session
from app.models.project import Project
from app.providers.resolver import (
    EmbeddingPinMismatch,
    ProviderResolutionError,
    UnsupportedCapability,
)
from app.rag import answer as answer_mod
from app.services.rate_limit import RateLimiter

router = APIRouter()
logger = logging.getLogger("documind.query")

# Per-user RAG rate limit (section 14: per-user RAG/ingest limits).
_query_limiter = RateLimiter(max_attempts=120, window_seconds=60.0)


def _error_frame() -> str:
    """A terminal SSE error frame with a FIXED message (never leaks provider/key
    detail). Keeps the stream well-formed when a provider/resolver error occurs
    after the 200 + headers have already been flushed."""
    payload = {
        "error": {
            "code": "provider_error",
            "message": "The answer service is temporarily unavailable. Please try again.",
        }
    }
    return f"event: error\ndata: {json.dumps(payload)}\n\n"


@router.post("", response_model=None)
async def query_project(
    project_id: uuid.UUID,
    payload: QueryRequest,
    request: Request,
    user: CurrentUser,
) -> StreamingResponse | JSONResponse:
    """Answer a question strictly from the project's chunks (SSE or JSON)."""
    if not _query_limiter.allow(f"query:{user.id}:{client_ip(request)}"):
        raise api_error(429, "rate_limited", "Too many questions; slow down.")

    question = payload.question.strip()
    if not question:
        raise api_error(422, "validation_error", "Question must not be empty.", field="question")

    # Verify project ownership up-front (a short, separate tenant transaction) so
    # a 404/409 surfaces as a normal HTTP error BEFORE any SSE body starts. The
    # check is idempotent; the answer path re-opens its own tenant session that
    # spans the whole stream and commits the persisted messages at the end.
    async with tenant_session(user.id, is_admin=False) as session:
        await _verify_project(session, user_id=user.id, project_id=project_id)

    if payload.stream:
        return _stream_response(
            project_id=project_id,
            user_id=user.id,
            question=question,
            conversation_id=payload.conversation_id,
        )
    return await _json_response(
        project_id=project_id,
        user_id=user.id,
        question=question,
        conversation_id=payload.conversation_id,
    )


async def _verify_project(
    session: AsyncSession, *, user_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise api_error(404, "not_found", "Project not found.")


def _resolution_error(exc: ProviderResolutionError) -> HTTPException:
    if isinstance(exc, EmbeddingPinMismatch):
        return api_error(409, "embedding_dim_mismatch", "Project embedding pin mismatch.")
    if isinstance(exc, UnsupportedCapability):
        return api_error(409, "capability_unsupported", str(exc))
    return api_error(502, "provider_error", "Provider resolution failed.")


def _stream_response(
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    conversation_id: uuid.UUID | None,
) -> StreamingResponse:
    async def _gen() -> AsyncIterator[str]:
        # One tenant transaction spans the whole stream; the full retrieved set
        # is captured by prepare_answer BEFORE any token is yielded, so no tenant
        # DB read happens mid-stream (section 8). Ownership was re-verified
        # up-front; re-check defensively inside the scoped session.
        #
        # The status (200) + headers are already flushed by the time this runs,
        # so a provider/resolver failure (before OR mid-stream) cannot become an
        # HTTP error — emit a well-formed terminal `error` frame instead of
        # truncating the body, and never serialize the raw provider/key detail.
        try:
            async with tenant_session(user_id, is_admin=False) as session:
                await _verify_project(session, user_id=user_id, project_id=project_id)
                plan = await answer_mod.prepare_answer(
                    session,
                    user_id=user_id,
                    project_id=project_id,
                    question=question,
                    conversation_id=conversation_id,
                )
                async for frame in answer_mod.stream_sse(
                    session, plan, user_id=user_id, project_id=project_id
                ):
                    yield frame
        except Exception:  # noqa: BLE001 - terminal error frame, never a truncated stream
            logger.exception("query stream failed (project %s)", project_id)
            yield _error_frame()

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _json_response(
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    conversation_id: uuid.UUID | None,
) -> JSONResponse:
    async with tenant_session(user_id, is_admin=False) as session:
        await _verify_project(session, user_id=user_id, project_id=project_id)
        try:
            plan = await answer_mod.prepare_answer(
                session,
                user_id=user_id,
                project_id=project_id,
                question=question,
                conversation_id=conversation_id,
            )
        except ProviderResolutionError as exc:
            raise _resolution_error(exc) from exc
        body = await answer_mod.answer_json(session, plan, user_id=user_id, project_id=project_id)
    return JSONResponse(content=body)


__all__ = ["router"]
