# ADR-0011: Infra and install — same-origin Caddy, prebuilt GHCR images, mandatory swap, idempotent installer

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
DocuMind targets self-hosting on a single, often small, VPS. The deployment must terminate TLS, serve a same-origin SPA + API (no CORS), run reliably on hosts with as little as 2GB RAM, avoid building heavy images on the VPS itself, and let an operator re-run the installer safely without clobbering their secrets or data. Postgres must be tuned for a memory-constrained box.

## Decision
A standalone **Caddy** service publishes host `80/443`, terminates TLS via ACME, and reverse-proxies a **same-origin apex domain**: `/api/*` → `api:8000` (prefix **not** stripped) and `/*` → `web:3000`, eliminating CORS. Application images are **public multi-arch images on GHCR** (`ghcr.io/${IMAGE_OWNER}/documind-api` and `.../documind-web`, default `IMAGE_OWNER=alighaemi9731`, `IMAGE_TAG=latest`) and are **never built on the VPS** — the VPS only pulls. On hosts with **≤2GB RAM a 2GB swapfile is mandatory** and created by the installer. The installer is **idempotent and secret-preserving**: re-running it regenerates nothing that already exists (`JWT_SECRET`, `MASTER_KEY_FERNET`, Postgres credentials are preserved) and is safe to run repeatedly. Postgres is tuned for the small target, notably `maintenance_work_mem=64MB` (e.g. to bound HNSW index builds).

## Consequences
Same-origin routing removes a whole class of CORS and cookie-SameSite headaches (supports ADR-0001). Prebuilt multi-arch GHCR images mean a `docker compose pull && up` deploy that does not need a compiler or large build memory on a 2GB box. The mandatory swapfile prevents OOM kills during ingest/index builds on tiny hosts. An idempotent, secret-preserving installer makes upgrades and re-runs non-destructive — operators can re-run without fear of rotating keys out from under encrypted data (ADR-0007). `maintenance_work_mem=64MB` keeps index builds within budget. Costs: `IMAGE_TAG=latest` favors simplicity over reproducibility (operators wanting pinned versions must override it); swap-on-disk is slower than RAM; CI must publish multi-arch images.

## Alternatives considered
Building images on the VPS (slow, memory-hungry, fails on 2GB hosts — rejected). Nginx + certbot for TLS/routing (more moving parts than Caddy's automatic ACME and inline reverse proxy — rejected). Separate API and web subdomains (reintroduces CORS and cross-site cookie complexity — rejected). An installer that always regenerates secrets (would orphan encrypted data on re-run — rejected).
