# ADR-0017: Chat history single-turn v1 — persist conversations, but retrieval is single-turn

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
DocuMind has a chat interface over the RAG corpus. There is a distinction between persisting conversation history (so the UI can show past Q&A and so the streamed `done` event can carry a real, durable `message_id`) and being history-aware during retrieval (rewriting the current query using earlier turns so follow-up questions like "what about the second one?" resolve correctly). Full multi-turn, history-aware retrieval is substantial work; we must decide how much of it lands in v1.

## Decision
**Persist conversations and messages** in v1: each turn is stored, so the SSE **`done` event's `message_id` refers to a real persisted message**, and the UI can render past Q&A from storage. However, **retrieval is single-turn in v1** — the current question alone drives retrieval, with **no history-aware query rewriting**. **Multi-turn follow-up context** (resolving a question against prior turns, query rewriting from conversation history) is explicitly **deferred to post-v1**.

## Consequences
The chat UI is fully functional for displaying history, and clients get a stable `message_id` they can reference (for citations, feedback, deletion), because the persistence layer is real, not a stub. Decoupling persistence from history-aware retrieval lets v1 ship a useful product without the complexity and failure modes of query rewriting (which can degrade grounding if done poorly — see ADR-0008). Costs: follow-up questions that depend on earlier turns ("explain that further", "the second option") will retrieve against only the literal follow-up text and may miss context, so users must phrase each question self-containedly in v1; the persistence schema must already model conversations/messages so the post-v1 multi-turn feature can build on it without a migration churn.

## Alternatives considered
No persistence at all (the `done` event's `message_id` would be synthetic, the UI couldn't show history — rejected). Full history-aware retrieval with query rewriting in v1 (significant scope, risks weakening the grounding gate, not required for an initial useful release — deferred to post-v1). Persist only the latest turn (loses the conversation view and stable message identity — rejected).
