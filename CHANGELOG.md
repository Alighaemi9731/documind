# Changelog

All notable changes to DocuMind are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — Landing & auth redesign

- **Immersive landing page** built entirely from the existing design tokens: a glass nav over a soft `--accent` aurora + masked grid, a two-column hero with a hand-authored **custom SVG** (`components/HeroArt.tsx`) animating "source documents → glowing answer beam → grounded answer with `[1] [2]` citation chips", an "Upload → Ask → Cited answer" step strip, the feature trio, and an aurora CTA band. Framer stays lazy (landing First-Load ~111 kB); RTL-correct; great in light + dark.
- **Auth screens** (login/register) restyled into an elevated split-panel with a branded aside (aurora + hero art on `lg+`); form logic untouched.
- **Sign out returns to the landing page** (`/`) instead of `/login`.

### Fixed

- **Session dropped on reload / silent-refresh 403 (CSRF cookie path).** The double-submit CSRF cookie was scoped to `/api/auth`, so the SPA's JS could not read it on app routes (`/projects`, `/settings`) to echo the `X-CSRF-Token` header — every silent refresh after the 15-min access token expired returned 403, bouncing the user to login on reload. The CSRF cookie is now scoped to `/` (it is a non-secret double-submit token; the httpOnly refresh cookie stays `/api/auth`-scoped), and login now also evicts any legacy `/api/auth`-scoped CSRF cookie.
- **Shared Gemini chat default returned 429 (`limit: 0`).** Google sets the free-tier `generate_content` quota for pinned models like `gemini-2.0-flash` to 0, so out-of-the-box Q&A failed. The default Gemini chat model is now the rolling `gemini-flash-latest` alias, which currently IS available on the free tier (embeddings were always fine).
- **Ingest worker crashed at startup without an operator key.** It resolved a single shared embedder from the operator-default key at boot (`secret.reveal()` on `None`), so a BYOK-only install never processed any document. The embedder is now resolved **per job** (per owner: BYOK → shared) inside the worker, which starts regardless of whether an operator key is seeded.
- **A working BYOK key could be marked invalid.** Key validation probed the chat capability, so a Gemini key whose free chat quota is exhausted (429) was flagged invalid and disabled even though its embeddings work. The probe now prefers the **embedding** capability (RAG-critical, far higher free-tier quota), falling back to chat only for chat-only providers.
- **Gemini empty/blocked completions no longer 500.** `response.text` is a property that raises when a candidate has no text part (e.g. a 1-token probe or a safety block); it is now read defensively as empty.
- **Uploads failed with a non-root container (permission denied).** The API image runs as the non-root `app` user, but the `uploads` named volume is created root-owned, so writing an upload to `/data/uploads` 500'd. `Dockerfile.api` now pre-creates `/data/uploads` owned by `app`, so a fresh volume inherits writable ownership. (Existing installs: `docker compose exec -u root api chown -R app:app /data/uploads` once.)
- **Bootstrap admin could not sign in.** `bootstrap-admin` creates the configured admin account without a password (expecting it to be claimed by self-registration), but `register` rejected the existing email outright — locking the operator out. The configured `ADMIN_EMAIL` can now **claim** its passwordless bootstrap account on first registration (sets the password, stays an active admin); the claim is scoped to that exact email (no account-takeover surface) and is one-shot (a later duplicate registration still 409s). Covered by two new tests.

### Added — Phase 6 (Install & SSL)

- **One-line installer (`install.sh`):** `curl -fsSL … | bash` → prompts for domain + admin email (+ optional Gemini key), or reads them from the environment for unattended installs. It is **idempotent**: secrets (`POSTGRES_PASSWORD`, `JWT_SECRET`, `MASTER_KEY_FERNET`) are CSPRNG-generated once and **preserved on re-run**, so a re-run upgrades in place without invalidating sessions or ACME certificates. Preflight covers Docker + the compose v2 plugin, an anonymous **GHCR manifest check** for both images, port-80 reachability, a soft DNS-vs-public-IP check, and a **mandatory 2 GB swapfile** on ≤2 GB hosts. It then `compose pull` → `up -d` → waits for Postgres → `alembic upgrade head` → seeds the operator key → ensures the bootstrap admin → waits for `/api/health/ready`, and finally probes public HTTPS — **surfacing the Caddy/ACME logs** when a certificate hasn't issued rather than only reporting success.
- **Automatic HTTPS:** Caddy obtains/renews Let's Encrypt certificates (HTTP-01); the installer wires `ACME_EMAIL` and supports a **staging-CA** mode (`DOCUMIND_ACME_STAGING=1`) so smoke tests on throwaway hosts don't burn the production rate limit. `caddy_data` (account + certs) is a named volume that survives restarts and is included in backups.
- **Backup/restore:** `deploy/backup/{backup,restore}.sh` snapshot the database + uploads + **`caddy_data`** together (so HTTPS survives a restore), with rotation; restore is a single command.
- **Docs:** a full [operating runbook](docs/operating.md) (install, day-2 ops, backup/restore, `MASTER_KEY_FERNET`/`JWT_SECRET` rotation, an **ACME/HTTPS troubleshooting table**, v1 limitations, upgrade/rollback, 2 GB resource notes), a rewritten README with the real install flow, and a screenshots pipeline (`e2e/screenshots.spec.ts` → `docs/screenshots/`).
- **DoD:** the end-to-end happy path (register → project → upload → ready → ask → grounded cited answer **or** the guarded refusal) is covered by the `RUN_E2E`-gated Playwright `chat.spec.ts`; `make test` runs backend + Vitest, `make web-e2e` runs Playwright against a live stack.

### Security (Phase 6 review hardening)

- **Backup integrity (review HIGH):** `backup.sh` now writes each artifact to a `*.partial` file, integrity-checks it (`gzip -t`), and only then atomically renames it into place — a truncated `pg_dump` (e.g. a mid-stream failure that `gzip` would otherwise swallow) can no longer become the "newest" backup and evict a good older one during rotation.
- **Restore safety (review HIGH):** `restore.sh` validates **both** input files before touching anything, then requires an interactive `yes` (skippable with `RESTORE_YES=1`); it stops `api` + `caddy`, **clears** the uploads/`caddy_data` volumes before extracting (an exact restore, not an overlay), and restarts them.
- **Installer robustness:** `DOMAIN` is format-validated and the `GEMINI_KEY`/`ADMIN_EMAIL` reject embedded whitespace before being written into the `.env` heredoc (no env-line injection); an existing correctly-sized `/swapfile` is reused rather than destroyed on re-run; backup/restore detect `docker compose` vs `docker-compose` and read only `POSTGRES_USER`/`POSTGRES_DB` from `.env` instead of exporting every secret.

### Added — Phase 5 (Frontend Polish & Admin Dashboard)

- **Apple-inspired design system:** a small, dependency-light component library (`components/ui/*` — Button, Field, Select, Card, Badge, Skeleton, Progress, Spinner, Modal, Toast, Tabs, Table, Nav, Logo, ThemeToggle, Sparkline) built on design-token CSS variables and Tailwind. Light/dark via a pre-hydration theme script (cookie-backed, **no flash**), and RTL via logical properties + a per-string direction resolver (Persian/English). Framer Motion is **lazy-loaded** (modal/toast/page transitions only) so it is never in the initial chunk — landing First-Load JS stays ~109 kB.
- **Full admin dashboard (`/admin`):** Users (search/promote/demote/disable with last-admin guard), Registrations (approve/reject + pending-count badge), Invites (copy-link delivery), Usage analytics (sparklines), per-user Quota, BYOK Keys metadata, Operator-key rotation, and install Settings — all over the metadata-only admin session (never document/chunk/message content).
- **Runtime branding:** `GET /api/config` now returns `branding {app_name, accent_color, logo_url}`; the UI renders `app_name` as **plain text**, applies `accent_color` via the **CSSOM** (`--accent` custom property, not an inline style — the strict no-`unsafe-inline`-script CSP holds), and only honors a **same-origin relative** `logo_url`. New admin endpoints `GET/PUT /api/admin/settings` (registration mode, default provider, signups toggle, default monthly token limit, branding) with `extra="forbid"`.
- **Tests:** 22 Vitest/Testing-Library component+a11y tests (Modal focus-trap + ARIA, direction resolver, apiClient single-flight, stream reader, branding allow-lists) alongside the 219 backend tests; Playwright moved to `test:e2e` (RTL/theme/admin specs, `RUN_E2E`-gated).

### Security (Phase 5 review hardening)

- **Accent-color validator parity (review HIGH):** the server's `accent_color` allow-list now mirrors the client's `normalizeAccent` **exactly** (3-/6-digit hex **or** an `H S% L%` triple — both free of CSS-breaking characters), closing a client/server mismatch where the admin UI could submit a value the API rejected. Branding is **re-validated on read** in `branding_from_stored` (accent dropped to default, logo dropped to None if unsafe) so a hand-edited row can never reach the DOM, and `app_name` is stripped of control characters.
- **Dialog a11y (review MEDIUM):** `Modal` now associates its name/description via `aria-labelledby`/`aria-describedby` (was a duplicated `aria-label`), and its Esc/focus-trap handler runs on a **document-level capture listener** so it works reliably across the portal boundary.

### Added — Phase 4 (BYOK + Providers)

- **Bring-your-own-key:** per-user encrypted key store (`provider_keys`, Fernet/MultiFernet at rest, **sha256-only fingerprints**, decrypted material wrapped in a redacting `Secret`). Settings API `GET/POST/DELETE /api/settings/keys` is **write-only** — no endpoint ever returns a key (plaintext or ciphertext); keys are validated once on save via an injectable, **rate-limited** health check against hard-coded provider base URLs (no SSRF).
- **Full provider set:** OpenAI (chat + `text-embedding-3-small`), **Anthropic** (chat-only, official SDK, `claude-opus-4-8`, adaptive thinking, **never** sends `budget_tokens`/`temperature`/`top_p`/`top_k`), Groq (chat-only), and local `bge-m3` (embedding-only, opt-in, ≥4 GB). Five new `ProviderSpec` rows; adding a provider is one spec row.
- **Two-tier resolver:** per-capability, independent BYOK→shared precedence (a user's BYOK chat can coexist with shared Gemini embeddings); embedding selection asserts the project's dim pin (409 on mismatch) and an embedding-provider change to a new dim triggers an explicit **re-embed** job (ADR-0015).
- **Quota (ADR-0009):** atomic pre-call reserve enforced **only** on the shared operator key (BYOK bypasses), with per-user monthly limits **and a true install-wide ceiling** (a separate atomic `install_usage` counter so the shared free-tier key can't be drained across all users); usage attributed per `key_source`. Graceful localized 429 directing the user to add their own key.
- **Admin (backend) + settings UI:** admin endpoints (users list/disable/promote/demote with last-admin guard, registrations approve/reject, invites, usage time-series, per-user quota, keys-metadata, operator-key rotate) over a metadata session that never touches document/chunk/message content; a settings page with masked key rows and per-capability provider/model selection. Master-key rotation CLI. Migration 0004.
- **Tests:** 215 backend tests pass against real pgvector — incl. a **secret-leak scan** (key never appears in any settings/admin response or logs), cross-tenant key/usage isolation, the install-wide ceiling across users, BYOK-bypass, key_source attribution, and the Anthropic adapter's forbidden-params assertion.

### Security (Phase 4 review hardening)

- **Admin RLS (review BLOCKER):** the Phase-4 metadata tables (keys/usage/quota/selections) now carry the `app.is_admin` bypass so admin oversight works under RLS `FORCE` — these are metadata, not content; the encrypted key is still never returned (ADR-0002).
- BYOK validation is now rate-limited per user/IP (was only TTL-cached); the global ceiling is now genuinely install-wide (was mistakenly per-user). Rate limiters self-register so tests reset them uniformly.

### Added — Phase 3 (RAG core)

- **Grounded, cited answers:** a project-scoped question is answered strictly from that project's chunks with server-validated citations, or refused ("not in your documents"). Hybrid retrieval = pgvector cosine + `tsvector('simple')` keyword fused by **RRF (k=60)** + a lightweight CPU rerank, all scoped `owner_id AND project_id AND embedding_dim`. The query embedding uses the same `text_norm` + `RETRIEVAL_QUERY` task type as ingest.
- **Grounding gate (ADR-0008):** the **raw best-chunk cosine similarity** (not the RRF rank score) is the sole trust anchor — an off-topic question is refused **before any LLM call** (localized fa/en). The model's `<<<GROUNDED…>>>` sentinel is advisory and fail-closed (never upgrades grounded false→true); the server strips it from the token stream (bounded-lookahead filter) and emits the authoritative `grounded` only in the `done` event.
- **Prompt-injection defenses:** operator instructions live in the system role; retrieved chunk text is fenced in per-request random-nonce delimiters and labeled untrusted; nonce/sentinel/fence-shaped strings inside chunk content are neutralized so a poisoned document cannot forge the fence, inject a sentinel, or exfiltrate.
- **Streaming + persistence:** `POST /api/projects/{id}/query` → SSE (`token*` → `citations` → `done`) with an identical JSON fallback; conversations/messages persisted (RLS `FORCE`, owner-only, no admin bypass) so `message_id` is durable (ADR-0017; single-turn retrieval). Migration 0003. Added a `GeminiChatProvider` (chat + streaming, SDK-error normalized).
- **Frontend chat:** streaming answers (fetch + ReadableStream, not EventSource — Bearer + single-flight refresh), inline citation chips, a sources panel, a distinct guarded "Not in your documents" state, and session history; model text rendered via safe markdown (HTML disabled).
- **Tests:** 169 backend tests pass against real pgvector — incl. grounded-cited answers, off-doc refusal **with no chat call**, forged-citation drop, **cross-tenant isolation** on retrieval/citations/messages, sentinel stripping across token boundaries, fa/en + ZWNJ retrieval, SSE order, and JSON-fallback parity.

### Fixed / Security (Phase 3 review hardening)

- **Sentinel stripper case bug:** the partial-sentinel hold-back compared an uppercase opener against a lowercased suffix, so a sentinel split across tokens leaked and grounded answers were wrongly marked ungrounded — fixed (now verified across every byte boundary).
- **SSE error handling (review HIGH):** a provider/resolver failure mid-stream previously truncated the body with no terminal frame; the stream now emits a well-formed `event: error` frame with a fixed message (no provider/key detail leaks), handled by the chat UI. Added a test asserting a raising chat provider yields a clean error frame.

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

- **Tenant isolation (dual-layer):** app-layer `TenantScope` as the sole tenant data path **+** Postgres RLS `FORCE`, driven by one hardened async session factory (`core/db.py`) that `SET LOCAL`s the tenant GUC per transaction (request **and** worker), **resets it on pool check-in**, and asserts it before tenant queries. The admin RLS bypass is confined to the `users` metadata table — tenant _content_ (`projects`, future docs/chunks) has owner-only policies with no bypass.
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
