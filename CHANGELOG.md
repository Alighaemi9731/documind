# Changelog

All notable changes to DocuMind are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 2 (Document Ingestion)
- **Pipeline:** upload → guards → parse → chunk → embed → store, driven by an in-process asyncio worker (ADR-0005) that claims `ingest_jobs` with `FOR UPDATE SKIP LOCKED` + lease, sets the tenant GUC from `job.owner_id`, and advances `DocumentStatus` (queued→parsing→chunking→embedding→ready). Documents/chunks tables have RLS `FORCE` with **owner-only policies and no admin bypass** (content tables).
- **Storage:** `chunks` use an unbounded pgvector **`halfvec`** column + a generated `tsvector('simple')` column; chunks are stamped server-side with `owner_id`/`project_id`/`embedding_dim` and reject dimension mismatches; per-dim partial HNSW index is built lazily (deferred, ADR-0003).
- **Provider slice (ADR-0014):** `LLMProvider`/`EmbeddingProvider` Protocols, a `ProviderSpec` registry, a per-capability two-tier resolver (operator-default Gemini for now; BYOK in Phase 4), Fernet keystore + env-seeded `operator_default`, and a Gemini embedding adapter (`gemini-embedding-001` @768, manual L2 normalize). Projects pin their embedding identity at creation.
- **API:** `POST/GET/DELETE /api/projects/{id}/documents`, `…/reprocess`, and public `GET /api/config`; per-user upload rate limit + pending-job cap.
- **Frontend:** `FileDropzone`, `StatusPill`, document-status polling (visibility-aware, stops on terminal), and a project view with upload + document list + reprocess/delete.
- **Tests:** 92 backend tests pass against real pgvector — parsers (incl. a Persian fixture), chunker, guards (each `DocumentErrorCode`), end-to-end embed/store with a deterministic fake embedder, dim-mismatch reject, ingest-job state machine + lease re-claim, worker GUC from `job.owner_id`, **document/chunk cross-tenant isolation**, and dedupe.

### Security (Phase 2 review hardening)
- Worker now fails poison jobs (catch-all → `failed`) instead of re-claiming forever, with an `attempts` ceiling + a reaper for crash-stuck jobs; the Gemini adapter normalizes SDK rate-limit/quota/5xx errors to a `ProviderTransientError` that the worker treats as a non-failing retry. DOCX XXE validation now covers **every** XML part (not just `document.xml`). Key fingerprints are sha256-only (no raw key tail). Reprocess clears stale embedding metadata and resets `attempts`.
- Known follow-up: the upload path still buffers the (capped) file once in RAM after streaming — a future optimization will compute the hash during the stream and guard from the file handle.

### Added — Phase 1 (Auth + Tenancy)
- **Tenant isolation (dual-layer):** app-layer `TenantScope` as the sole tenant data path **+** Postgres RLS `FORCE`, driven by one hardened async session factory (`core/db.py`) that `SET LOCAL`s the tenant GUC per transaction (request **and** worker), **resets it on pool check-in**, and asserts it before tenant queries. The admin RLS bypass is confined to the `users` metadata table — tenant *content* (`projects`, future docs/chunks) has owner-only policies with no bypass.
- **Auth:** argon2id passwords (rehash-on-login, semaphore-bounded), HS256 JWTs with pinned-algorithm decode + `token_version` revocation, opaque sha256-hashed refresh tokens with rotation, family reuse-detection, a grace window, and chain-advance replay detection. `REGISTRATION_MODE` = open | approval | invite, bootstrap-admin reconciliation, per-IP **and** per-email login rate limiting.
- **Transport (ADR-0001):** in-memory Bearer access token + httpOnly/Secure/SameSite=Lax refresh cookie (Path `/api/auth`) + double-submit CSRF + HTTPS-only, fail-closed Origin allow-list.
- **API:** `/api/auth/{register,login,refresh,logout,me}` and projects CRUD, all tenant-scoped; canonical `{error:{code,message,field?}}` envelope via app-wide exception handlers; SQLAlchemy models + the `0001` Alembic migration (tables, PG enums, extensions, RLS policies); `python -m app.cli bootstrap-admin`.
- **Frontend:** auth shells (login/register adapting to registration mode, dashboard projects list), in-memory-token api client with single-flight silent refresh + CSRF header, `next dev` → backend rewrite, security-headers/CSP-nonce middleware (client-side auth guard is authoritative).
- **Tests:** 42 backend tests green against real Postgres/pgvector — including the **pooled-connection stale-GUC cross-tenant leak test** (run as a non-superuser RLS role), all registration modes, refresh rotation/reuse, and projects cross-tenant 404.

### Security (Phase 1 review hardening)
- Removed the RLS admin-bypass from tenant content tables and forced the request path to `is_admin=false` (the highest-risk finding); made the CSRF Origin check fail-closed and HTTPS-only; added refresh chain-advance replay detection; stopped resetting the login limiter on success; guarded the RLS uuid cast against an empty GUC; validate the Fernet master key and gate the test-env secret skip to actual pytest runs. Removed a shadowed/incorrect frontend cookie-proxy route handler in favor of direct same-origin calls.

### Added — Phase 0 (Scaffolding)
- Monorepo layout: `apps/api` (FastAPI), `apps/web` (Next.js standalone), `deploy/`, `docs/`.
- `deploy/`: production `docker-compose.yml` (+ dev override), `Caddyfile` (automatic HTTPS, same-origin `/api` + `/*` routing, SSE flush, body cap, security headers), low-RAM Postgres tuning, Postgres extension init (`vector`, `pg_trgm`, `unaccent`, `citext`), and `backup`/`restore` scripts.
- `apps/api`: FastAPI skeleton with `GET /api/health/live` and `GET /api/health/ready` (DB + `vector` extension checks, degrades gracefully), pydantic-settings config, async Alembic scaffold, and a health test.
- `apps/web`: Next.js 15 App Router + TypeScript + Tailwind 3.4 standalone skeleton, security-headers/CSP-nonce middleware, CSS-variable design tokens, and a gated Playwright smoke test.
- Multi-stage Dockerfiles for api and web (non-root, healthchecks, small footprint).
- CI (`ci.yml`: ruff/format/mypy/pytest, eslint/prettier/tsc/build, `docker compose config`), image publishing to public GHCR (`images.yml`), and security scanning (`security.yml`: gitleaks, trivy, hadolint).
- Claude Code hooks: PreToolUse secret-scan commit gate + PostToolUse formatter.
- `ARCHITECTURE.md`, 17 ADRs (`docs/decisions/`), `docs/operating.md` runbook stub.
- Root tooling: `Makefile`, `.env.example`, `CLAUDE.md`, AGPL-3.0 `LICENSE`, `README.md`.

### Notes
- Verified locally: backend lint (ruff) + health test, frontend lint/typecheck. Full
  `docker compose up`, end-to-end installer, and the VM HTTPS smoke are exercised in
  CI / on a throwaway VM (Docker daemon not assumed on the dev box).

[Unreleased]: https://example.com/documind/compare/HEAD
