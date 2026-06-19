# ADR-0002: Tenant isolation — dual-layer app TenantScope plus Postgres RLS FORCE

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
DocuMind is multi-tenant: every document, chunk, conversation, and usage event belongs to exactly one user/tenant, and a cross-tenant read of document or chunk content is a catastrophic confidentiality failure. A single isolation mechanism is one bug away from a leak. Both the request path and the background ingest worker share the same models and connection pool, so any isolation scheme must apply identically to both.

## Decision
Two independent layers enforced through ONE hardened async session factory. Layer 1 (primary, the only code path that reads tenant data) is an application-level `TenantScope` that filters every tenant query by the current user id. Layer 2 (fail-safe) is Postgres Row-Level Security with `FORCE ROW LEVEL SECURITY` on tenant tables, keyed off `current_setting('app.current_user_id')`. The session factory: (1) executes `SET LOCAL app.current_user_id = :uid` at transaction start for both request handlers and the ingest worker; (2) `RESET`s the GUC on pool check-in so a recycled connection can never inherit a prior tenant's id; (3) asserts `current_setting('app.current_user_id') == expected_uid` immediately before any tenant query and fails hard (raises) on mismatch. Admin operations may use an RLS-bypass role for metadata, but that bypass is never granted on the document/chunk content path.

## Consequences
A leak now requires both the app filter AND the RLS policy to fail simultaneously for the same query — defence in depth. `SET LOCAL` is transaction-scoped so it cannot leak across transactions; the explicit RESET-on-checkin guards against driver edge cases. The GUC equality assertion catches programming errors (a query issued outside a scoped transaction) loudly rather than silently returning wrong rows. Cost: every tenant transaction pays a `SET LOCAL` + assertion; the session factory becomes a single, security-critical chokepoint that must be tested heavily.

## Alternatives considered
App-layer filtering only (one missing `.filter()` leaks everything — rejected). RLS only (ORM lazy-loads or raw queries that forget to set the GUC silently return nothing or, worse, everything under a bypass role — rejected as sole mechanism). Schema-per-tenant or database-per-tenant (operationally heavy for a self-hosted install, complicates migrations and the shared `vector` extension — rejected for v1).
