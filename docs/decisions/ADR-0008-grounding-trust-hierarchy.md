# ADR-0008: Grounding trust hierarchy — raw cosine gate is the sole anchor, model sentinel is advisory

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
A RAG system must refuse to answer when the corpus does not actually support the question, otherwise it hallucinates with citations. Two signals are available to decide "is this grounded?": a retrieval score, and the model's own self-assessment. Retrieval combines dense and lexical results via reciprocal rank fusion (RRF), but the RRF rank score is a fused ordering signal, not a calibrated measure of semantic closeness. Letting the model decide grounding is unsafe — a model can claim grounding for a fabricated answer.

## Decision
The **sole trust anchor** is the **raw best-chunk cosine similarity** between the query embedding and the single closest retrieved chunk, compared against a **per-language calibrated threshold** (default `GROUNDING_MIN_SCORE = 0.55`). This is deliberately **not** the post-RRF rank score. If the raw best-chunk similarity is below threshold, the request is **refused before any LLM call** (saving tokens and preventing hallucination). The model emits a `<<<GROUNDED:...>>>` **sentinel** as an **advisory, fail-closed** signal: it can never upgrade `grounded=false` to `true`, only corroborate or downgrade. The server **strips the sentinel from the streamed output** and emits the **authoritative `grounded` value only in the final `done` event**. Every citation the model produces is **server-validated against the actual retrieved `chunk_id` set**; citations to chunks not retrieved are rejected.

## Consequences
Grounding is decided by a number the model cannot influence, computed before the model runs, so a confident hallucination cannot pass as grounded. Refusing before the LLM call is cheaper and safer than refusing after. The fail-closed sentinel lets the model veto a borderline answer without ever being able to manufacture grounding. Stripping the sentinel and emitting `grounded` only in `done` means clients trust one server-controlled field, not scraped text. Citation validation prevents invented references. Costs: the per-language threshold must be calibrated and maintained; raw cosine on a single best chunk can occasionally refuse answerable questions whose support is spread thinly across many chunks (a recall trade-off accepted in favor of precision).

## Alternatives considered
Using the post-RRF rank score as the gate (fused rank is not a calibrated similarity; a high rank among weak results still means weak grounding — explicitly rejected). Trusting the model's `GROUNDED` claim as authoritative (lets the model self-certify hallucinations — rejected). A global single threshold across all languages (Persian/English score distributions differ — rejected in favor of per-language calibration).
