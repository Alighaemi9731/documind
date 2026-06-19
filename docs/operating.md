# DocuMind Operating Runbook

> STUB — Phase 0. Each section below is a placeholder to be fleshed out in Phase 6.

## Overview
DocuMind is a self-hostable, multi-tenant RAG platform deployed via Docker Compose (services: `caddy`, `api`, `web`, `postgres`). This runbook is the operator's reference for backup, secret rotation, TLS troubleshooting, known limitations, and upgrades. (To be expanded in Phase 6.)

## Backup & restore (pg_dump + uploads + caddy_data)
Back up three things together: the Postgres database (`pg_dump` of `documind`), the uploaded-documents volume, and Caddy's `caddy_data` (ACME certs/keys so HTTPS survives a restore). Restore order and consistency notes to be documented in Phase 6.

## Rotate secrets (MASTER_KEY_FERNET via MultiFernet, JWT_SECRET)
`MASTER_KEY_FERNET` rotates via MultiFernet: add the new key alongside the old, re-encrypt at-rest secrets (operator default key + BYOK keys), then retire the old key. `JWT_SECRET` rotation invalidates outstanding access/refresh tokens (users re-authenticate). Step-by-step procedure to be documented in Phase 6.

## ACME / HTTPS failure runbook (DNS not propagated, port 80 unreachable, Let's Encrypt rate limits, staging endpoint)
Common causes when Caddy cannot obtain a certificate: DNS for `DOMAIN` not yet propagated; inbound port 80 blocked/unreachable (ACME HTTP challenge fails); Let's Encrypt rate limits hit after repeated failures (use the staging endpoint while debugging, then switch back to production). Diagnostics and fixes to be documented in Phase 6.

## Known limitations (no OCR for image-only PDFs in v1, no SMTP in v1)
No OCR in v1: image-only (scanned) PDFs with no embedded text layer will not be ingested as text. No SMTP in v1 (ADR-0016): invites are copyable links relayed by the operator; approval is in-app (pending state + admin badge). Full list to be expanded in Phase 6.

## Upgrading
Upgrades pull new prebuilt GHCR images (`IMAGE_TAG`) and re-run the idempotent, secret-preserving installer; existing secrets and data are preserved (ADR-0011). Migration and rollback details to be documented in Phase 6.
