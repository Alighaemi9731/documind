# ADR-0003: Embedding/vector contract — unbounded halfvec, per-project pin, deferred per-dim HNSW

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
Different embedding providers and models emit vectors of different dimensionality and different normalization conventions, and a single install may host projects pinned to different models over time. pgvector's `vector` type caps at 2000 dimensions and stores float32; modern embedding models (and future ones) can exceed that or benefit from half-precision storage. We need a storage and indexing scheme that survives model heterogeneity without a schema migration per model, and that does not pay index-build cost before any data exists.

## Decision
Store embeddings in an **unbounded `halfvec`** column (half-precision, no fixed-dimension declaration on the column), so a single table holds vectors of any dimensionality. Each project carries an immutable embedding pin: `{provider, model, dim, normalized}`. The default pin is `gemini-embedding-001 @ 768` with `normalized=true`, and because the provider does not guarantee unit vectors we apply a **manual L2 normalization** at ingest and query time so cosine and inner-product distances agree. Indexing is **deferred**: HNSW indexes are built lazily, **per dimension**, as **partial indexes** (`WHERE dim = N`) with `m=16, ef_construction=64`, and only after the first ingest for that dimension. Until then, queries fall back to exact scan (acceptable at small corpus sizes).

## Consequences
One column serves all models; adding a new model is a pin change, not a migration. `halfvec` roughly halves index and storage footprint, which matters on the 2GB-RAM target VPS. Per-dim partial HNSW means a project on 768-dim vectors gets an index tuned to its dimension without other dimensions polluting it, and a brand-new install pays zero index cost. Trade-offs: half-precision sacrifices a little recall versus float32 (acceptable for RAG ranking); deferred indexing means the very first queries on a fresh project are exact-scan and slower; the per-dim partial-index strategy adds bookkeeping owned by the data-model layer (see ADR-0015).

## Alternatives considered
Fixed-dimension `vector(768)` column (forces a migration or a second table per model — rejected). Float32 `vector` everywhere (2000-dim cap and double the memory — rejected). Eager HNSW at project creation (wasted build on empty projects, and you cannot build a dimension-correct index before you know the dimension — rejected). Skipping normalization and relying on inner product (mixes poorly across models with differing norms — rejected).
