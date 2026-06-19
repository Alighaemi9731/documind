# ADR-0014: Phase-ordering — pull a minimal Gemini provider slice forward into Phase 2

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
DocuMind is built in phases. The provider abstraction, the operator key, and per-project embedding pins (ADR-0003, ADR-0006, ADR-0007) naturally belong to a later "providers" phase (Phase 4). But ingestion needs real embeddings to produce vectors, and the project's Definition of Done depends on an end-to-end ingest → embed → store → retrieve path working earlier than Phase 4. If the provider stack only arrives in Phase 4, nothing meaningful can be embedded or retrieved before then, and the DoD is unreachable until very late.

## Decision
Pull a **minimal Gemini provider slice forward into Phase 2**: the provider **interfaces** (the `LLMProvider`/`EmbeddingProvider` Protocols), a **Gemini adapter**, the **two-tier resolver**, the **operator-default key** mechanism, and the **per-project embedding-pin columns**. This is the smallest vertical cut of the provider system that lets Phase 2 actually embed text with the default `gemini-embedding-001 @ 768` pin. The remaining provider work (additional adapters, BYOK UI, full capability matrix, quota wiring) stays in later phases.

## Consequences
A working ingest-and-retrieve path exists by Phase 2, making the Definition of Done reachable well before Phase 4 and allowing the retrieval, grounding (ADR-0008), and data-model phases to be exercised against real vectors rather than stubs. The slice is deliberately minimal — one provider, one capability path — to limit how much of the provider system is committed early. Costs: a small amount of provider scaffolding lands before its "natural" phase, so it must be designed to extend cleanly rather than be rewritten when the full provider phase arrives; the embedding-pin columns are introduced in Phase 2's schema, which the data-model phase must then build on (coordinated with ADR-0015).

## Alternatives considered
Keep the entire provider stack in Phase 4 (leaves Phases 2–3 unable to embed real content; DoD unreachable until late; lots of throwaway stubs — rejected). Use a fake/random-vector embedder until Phase 4 (makes retrieval and grounding untestable for real, and the throwaway code is wasted — rejected). Build all providers up front (over-invests early in a system whose full shape is still settling — rejected in favor of the minimal slice).
