"""Answer orchestration (section 8 / ADR-0008) — retrieve, gate, stream, cite.

This is the chokepoint that ties the RAG core together for one question:

1. Normalize the question; run the vector + keyword legs (full retrieved set
   captured BEFORE streaming — no tenant DB reads mid-stream).
2. Grounding gate (ADR-0008): if the raw best-chunk cosine < threshold, REFUSE
   before any LLM call with a localized refusal; the chat provider is never
   invoked.
3. Otherwise fuse (RRF) -> rerank -> budget-pack -> nonce-fenced prompt.
4. Resolve the chat provider; stream tokens through :class:`SentinelStripper`
   so the literal sentinel never reaches the client.
5. Server-validate every cited id against the retrieved chunk-id set; build the
   canonical Citation[].
6. Persist the user + assistant messages (+ validated citations + grounded) so
   ``message_id`` is real (ADR-0017).

Two surfaces share one prepared :class:`AnswerPlan`: :func:`stream_sse` (SSE) and
:func:`answer_json` (JSON fallback). Retrieval is idempotent, so the JSON
fallback reproduces identical citations.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text_norm import normalize
from app.models.conversation import Conversation
from app.models.enums import Capability, MessageRole
from app.models.message import Message
from app.providers import resolver
from app.rag import grounding
from app.rag.budget import PackedChunk, pack_context
from app.rag.citations import citations_from_answer
from app.rag.injection import make_nonce
from app.rag.prompt import build_prompt
from app.rag.retrieval.fuse import fuse_rrf
from app.rag.retrieval.keyword import keyword_search
from app.rag.retrieval.rerank import rerank
from app.rag.retrieval.vector import vector_search
from app.rag.sentinel import SentinelStripper
from app.services import quota_service

# Max output tokens for the synthesis call (bounds connection hold, section 8).
ANSWER_MAX_TOKENS = 1024


@dataclass
class AnswerPlan:
    """Everything decided BEFORE the LLM call: retrieval + grounding + prompt.

    Captured for one request so streaming never re-reads tenant data. When
    ``retrieval_ok`` is False this is a refusal and ``packed``/``prompt`` are
    empty (the chat provider must not be invoked).
    """

    question: str
    conversation_id: uuid.UUID
    retrieval_ok: bool
    refusal_text: str
    packed: list[PackedChunk]
    retrieved_ids: set[uuid.UUID]
    system_prompt: str
    user_prompt: str
    provider_id: str
    model: str
    adapter: Any  # LLMProvider; Any to avoid importing the Protocol at runtime
    # Quota reservation made BEFORE the LLM call (None on a refusal — no call).
    reservation: quota_service.Reservation | None = None
    project_id: uuid.UUID | None = None


async def _ensure_conversation(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    title: str,
) -> uuid.UUID:
    """Return an existing owned conversation id or create a new one."""
    if conversation_id is not None:
        existing = await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.owner_id == user_id,
                Conversation.project_id == project_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return row.id

    conversation = Conversation(
        project_id=project_id,
        owner_id=user_id,
        title=title[:512] or None,
    )
    session.add(conversation)
    await session.flush()
    return conversation.id


async def prepare_answer(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    question: str,
    conversation_id: uuid.UUID | None,
) -> AnswerPlan:
    """Run retrieval + the grounding gate and build the prompt (no LLM call).

    Resolves the chat provider only when grounded (so a refusal never touches a
    chat key). The full retrieved set is captured here, before any streaming.
    """
    query_norm = normalize(question)

    conv_id = await _ensure_conversation(
        session,
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
        title=question,
    )

    vector_hits = await vector_search(
        session, user_id=user_id, project_id=project_id, query_norm=query_norm
    )
    keyword_hits = await keyword_search(
        session, user_id=user_id, project_id=project_id, query=question
    )

    retrieval_ok = grounding.retrieval_grounded(vector_hits)
    if not retrieval_ok:
        # Refuse BEFORE any LLM call (ADR-0008). No provider resolution.
        return AnswerPlan(
            question=question,
            conversation_id=conv_id,
            retrieval_ok=False,
            refusal_text=grounding.refusal_message(question),
            packed=[],
            retrieved_ids=set(),
            system_prompt="",
            user_prompt="",
            provider_id="",
            model="",
            adapter=None,
        )

    fused = fuse_rrf(vector_hits, keyword_hits)
    reranked = rerank(fused, query=question)
    packed = pack_context(reranked)
    retrieved_ids = {item.row.chunk_id for item in packed}

    nonce = make_nonce()
    built = build_prompt(question, packed, nonce=nonce)

    resolved = await resolver.resolve_chat(session, user_id)

    # Quota seam (ADR-0009): atomic pre-call reserve, enforced only on the shared
    # operator key; BYOK chat bypasses. Reserved here, BEFORE the LLM call;
    # reconciled in _persist_turn against the actual token usage.
    reservation = await quota_service.check_and_reserve(
        session, user_id=user_id, key_source=resolved.key_source
    )

    return AnswerPlan(
        question=question,
        conversation_id=conv_id,
        retrieval_ok=True,
        refusal_text="",
        packed=packed,
        retrieved_ids=retrieved_ids,
        system_prompt=built.system,
        user_prompt=built.user,
        provider_id=resolved.provider_id,
        model=resolved.model,
        adapter=resolved.adapter,
        reservation=reservation,
        project_id=project_id,
    )


@dataclass
class AnswerResult:
    """The fully-assembled answer (used by the JSON fallback + persistence)."""

    answer: str
    citations: list[dict[str, Any]]
    grounded: bool
    provider: str
    used_chunks: list[str]
    input_tokens: int
    output_tokens: int


def _run_stream(plan: AnswerPlan) -> tuple[list[str], SentinelStripper, str]:
    """Drive the provider stream through the stripper; return (deltas, stripper, raw).

    ``deltas`` are the sentinel-stripped pieces safe to emit to the client (in
    order). ``raw`` is the full un-stripped model text (used for citation
    parsing, since the model cites by header inside the body). The stripper holds
    the fail-closed model-grounded verdict.
    """
    stripper = SentinelStripper()
    deltas: list[str] = []
    raw_parts: list[str] = []
    for delta in plan.adapter.chat_stream(
        [{"role": "user", "content": plan.user_prompt}],
        model=plan.model,
        system=plan.system_prompt,
        max_tokens=ANSWER_MAX_TOKENS,
    ):
        raw_parts.append(delta.text)
        safe = stripper.feed(delta.text)
        if safe:
            deltas.append(safe)
    tail = stripper.flush()
    if tail:
        deltas.append(tail)
    return deltas, stripper, "".join(raw_parts)


def _assemble_result(
    plan: AnswerPlan,
    *,
    deltas: list[str],
    stripper: SentinelStripper,
    raw_text: str,
) -> AnswerResult:
    answer_text = "".join(deltas)
    citations = citations_from_answer(raw_text, plan.packed, plan.retrieved_ids)
    grounded = grounding.final_grounded(
        retrieval_ok=plan.retrieval_ok, model_grounded=stripper.model_grounded
    )
    return AnswerResult(
        answer=answer_text,
        citations=citations,
        grounded=grounded,
        provider=plan.provider_id,
        used_chunks=[str(cid) for cid in sorted(plan.retrieved_ids, key=str)],
        input_tokens=0,
        output_tokens=0,
    )


async def _persist_turn(
    session: AsyncSession,
    plan: AnswerPlan,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    result: AnswerResult,
    grounded: bool | None,
    provider: str | None,
) -> uuid.UUID:
    """Persist the user + assistant messages; return the assistant message id."""
    session.add(
        Message(
            conversation_id=plan.conversation_id,
            owner_id=user_id,
            project_id=project_id,
            role=MessageRole.user,
            content=plan.question,
        )
    )
    assistant = Message(
        conversation_id=plan.conversation_id,
        owner_id=user_id,
        project_id=project_id,
        role=MessageRole.assistant,
        content=result.answer,
        grounded=grounded,
        provider=provider,
        citations=result.citations,
    )
    session.add(assistant)
    await session.flush()

    # Reconcile the shared-key quota reservation against actual usage + record the
    # UsageEvent (no-op for BYOK beyond the analytics row). Only when the chat
    # provider was actually invoked (a refusal carries no reservation).
    if plan.reservation is not None:
        await quota_service.record_usage(
            session,
            reservation=plan.reservation,
            provider=result.provider or plan.provider_id,
            capability=Capability.chat,
            project_id=plan.project_id if plan.project_id is not None else project_id,
            tokens_in=result.input_tokens,
            tokens_out=result.output_tokens,
        )
    return assistant.id


def _sse(event: str, data: Any) -> str:
    """Render one SSE frame: ``event: <name>\\ndata: <json>\\n\\n``."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_sse(
    session: AsyncSession,
    plan: AnswerPlan,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> AsyncIterator[str]:
    """Yield SSE frames: token* -> citations -> done.

    On a refusal (``retrieval_ok`` False) the chat provider is never invoked: the
    refusal text is emitted as a single token, no citations, ``grounded=false``.
    The user + assistant turns are persisted so ``message_id`` is real.
    """
    if not plan.retrieval_ok:
        refusal = AnswerResult(
            answer=plan.refusal_text,
            citations=[],
            grounded=False,
            provider="",
            used_chunks=[],
            input_tokens=0,
            output_tokens=0,
        )
        message_id = await _persist_turn(
            session,
            plan,
            user_id=user_id,
            project_id=project_id,
            result=refusal,
            grounded=False,
            provider=None,
        )
        yield _sse("token", {"text": plan.refusal_text})
        yield _sse("citations", [])
        yield _sse(
            "done",
            {
                "grounded": False,
                "provider": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "message_id": str(message_id),
            },
        )
        return

    deltas, stripper, raw_text = _run_stream(plan)
    result = _assemble_result(plan, deltas=deltas, stripper=stripper, raw_text=raw_text)

    message_id = await _persist_turn(
        session,
        plan,
        user_id=user_id,
        project_id=project_id,
        result=result,
        grounded=result.grounded,
        provider=result.provider,
    )

    for piece in deltas:
        yield _sse("token", {"text": piece})
    yield _sse("citations", result.citations)
    yield _sse(
        "done",
        {
            "grounded": result.grounded,
            "provider": result.provider,
            "usage": {
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
            "message_id": str(message_id),
        },
    )


async def answer_json(
    session: AsyncSession,
    plan: AnswerPlan,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> dict[str, Any]:
    """JSON-fallback path producing identical content to the SSE stream.

    ``{answer, citations, grounded, used_chunks, provider, message_id}``
    (section 6). Retrieval is idempotent, so citations match the streamed run.
    """
    if not plan.retrieval_ok:
        refusal = AnswerResult(
            answer=plan.refusal_text,
            citations=[],
            grounded=False,
            provider="",
            used_chunks=[],
            input_tokens=0,
            output_tokens=0,
        )
        message_id = await _persist_turn(
            session,
            plan,
            user_id=user_id,
            project_id=project_id,
            result=refusal,
            grounded=False,
            provider=None,
        )
        return {
            "answer": plan.refusal_text,
            "citations": [],
            "grounded": False,
            "used_chunks": [],
            "provider": None,
            "message_id": str(message_id),
        }

    deltas, stripper, raw_text = _run_stream(plan)
    result = _assemble_result(plan, deltas=deltas, stripper=stripper, raw_text=raw_text)
    message_id = await _persist_turn(
        session,
        plan,
        user_id=user_id,
        project_id=project_id,
        result=result,
        grounded=result.grounded,
        provider=result.provider,
    )
    return {
        "answer": result.answer,
        "citations": result.citations,
        "grounded": result.grounded,
        "used_chunks": result.used_chunks,
        "provider": result.provider,
        "message_id": str(message_id),
    }


__all__ = [
    "ANSWER_MAX_TOKENS",
    "AnswerPlan",
    "AnswerResult",
    "prepare_answer",
    "stream_sse",
    "answer_json",
]
