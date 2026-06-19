# Changelog

All notable changes to DocuMind are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
