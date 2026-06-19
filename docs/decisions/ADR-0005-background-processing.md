# ADR-0005: Background processing — in-process asyncio worker with DB job queue, Redis opt-in

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
Document ingestion (parse, chunk, normalize, embed, index) is long-running and must not block API request handlers. The default deployment target is a small single VPS, possibly with only 2GB RAM. Forcing every operator to run a Redis broker plus separate worker containers for a low-volume self-hosted RAG install is disproportionate, but heavier installs may want true horizontal worker scaling.

## Decision
The default profile runs an **in-process `asyncio` worker** inside the API container, backed by an **`ingest_jobs` table in Postgres** as the queue. Workers claim jobs with `SELECT ... FOR UPDATE SKIP LOCKED` plus a **lease** (a claimed-at / lease-expiry column) so a crashed worker's job becomes reclaimable rather than stuck. Concurrency is bounded by `INGEST_CONCURRENCY` (default 1). **No Redis** is required in the default profile. For installs that want dedicated, scalable workers, an **opt-in `worker` Compose profile** adds RQ + Redis; this profile is gated behind a documented `>=4GB` RAM recommendation.

## Consequences
A fresh `docker compose up` needs only `api`, `web`, `postgres`, and `caddy` — no broker — which keeps the 2GB target viable. The DB-as-queue with `FOR UPDATE SKIP LOCKED` + lease gives at-least-once delivery, crash recovery, and visibility (jobs are inspectable rows) without a second datastore. `INGEST_CONCURRENCY=1` keeps memory predictable on small hosts. Costs: the in-process worker shares the API's CPU and memory, so a heavy ingest can degrade request latency on a tiny box (mitigated by low concurrency and the upgrade path); polling a DB table is slightly less efficient than a push broker; two execution models (in-process vs RQ) must be kept behaviorally consistent.

## Alternatives considered
Redis/RQ or Celery as the only option (mandatory broker contradicts the lean default — rejected as default). Cron-driven batch processing (poor latency, no per-job leasing — rejected). A pure asyncio in-memory queue with no DB persistence (jobs lost on restart, no visibility, no multi-worker coordination — rejected).
