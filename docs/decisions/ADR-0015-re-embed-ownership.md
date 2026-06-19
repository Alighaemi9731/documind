# ADR-0015: Re-embed ownership — ingestion orchestrates, data-model owns schema/state and index swap

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
A project's embedding pin (ADR-0003) may change — for example, switching to a different model or dimensionality. When that happens, existing chunks were embedded under the old pin and must be re-embedded, and the per-dim HNSW index must be rebuilt for the new dimension. This crosses two subsystems: ingestion (which runs the work) and the data model (which owns the schema, the document/chunk state machine, and the indexes). Unclear ownership of who drives versus who mutates schema leads to half-migrated corpora and inconsistent indexes.

## Decision
Split responsibilities. **Ingestion drives orchestration and status**: it sequences the re-embed job, processes chunks, and reports progress/state transitions. The **data model owns the schema, the state machine, and the per-dimension index build/swap**: it defines valid states, performs the HNSW build for the new dimension, and atomically swaps it in. A **cross-dimension embedding switch is blocked with HTTP 409** on the normal ingest path — you cannot silently mix dimensions in place. Changing dimension requires an **explicit re-embed job** implemented as **delete-then-insert** (old-dimension vectors are removed and new-dimension vectors written), not an in-place update of mismatched vectors.

## Consequences
Each subsystem owns what it is best placed to own: ingestion sequences work and surfaces status; the data model guards schema invariants and index correctness, including the per-dim partial-index strategy from ADR-0003. Blocking cross-dim switches with a 409 prevents a half-migrated table where some chunks are 768-dim and others are not, which would corrupt retrieval and index assumptions. The explicit delete-then-insert re-embed job makes the migration a deliberate, observable operation rather than an accidental side effect. Costs: re-embedding the whole corpus re-spends embedding tokens/quota (ADR-0009) and takes time proportional to corpus size; during the job the project may have reduced or exact-scan retrieval until the new index is built and swapped; the two-subsystem split requires a clear interface so ingestion and data-model do not both try to mutate index state.

## Alternatives considered
Let ingestion mutate schema and indexes directly (blurs ownership, risks inconsistent indexes — rejected). Allow in-place cross-dim switches (produces a mixed-dimension table that breaks retrieval — explicitly rejected, returns 409). Update vectors in place rather than delete-then-insert (fragile across dimension changes and harder to make atomic — rejected). Maintain old and new embeddings side by side indefinitely (doubles storage and index cost — rejected for v1).
