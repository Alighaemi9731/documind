# ADR-0001: Auth transport — in-memory access JWT plus path-scoped refresh cookie

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
DocuMind is a same-origin SPA (Next.js web on `:3000`, FastAPI on `:8000`, both behind Caddy on one apex domain, no CORS). We must authenticate browser sessions against the API while resisting both XSS token theft and CSRF. The two classic failure modes are: (a) storing a long-lived bearer token in `localStorage`, which any injected script can exfiltrate; and (b) relying purely on cookies, which the browser attaches automatically and thus exposes to cross-site request forgery.

## Decision
Issue a short-lived access JWT (TTL 15 min, signed HS256 with a pinned algorithm — the verifier rejects any `alg` other than HS256 to prevent `alg:none` and confusion attacks). The access token lives only in JavaScript memory (never `localStorage`, never a cookie) and is sent as a `Authorization: Bearer` header. Issue a refresh token as an `httpOnly; Secure; SameSite=Lax` cookie, `Path`-scoped to `/api/auth/refresh` and `/api/auth/logout` so it is never attached to any other request. Refresh and logout additionally require double-submit CSRF (a readable CSRF cookie echoed in a header, compared server-side) plus an Origin/Referer allow-list check restricted to the configured apex domain (`PUBLIC_BASE_URL`). TTLs come from `ACCESS_TOKEN_TTL_MINUTES` (15) and `REFRESH_TOKEN_TTL_DAYS` (30).

## Consequences
XSS cannot read the refresh token (httpOnly) and the access token dies in 15 minutes and never persists across reloads, so a page refresh triggers a silent refresh call. CSRF is blocked on the only cookie-bearing endpoints by both the double-submit token and the Origin allow-list. The cost is more moving parts (silent-refresh logic on the client, CSRF plumbing) and that an in-memory access token is lost on reload until refresh completes.

## Alternatives considered
Bearer token in `localStorage` (simplest, but XSS-exfiltratable — rejected). Pure session cookie for everything (CSRF-prone and couples API to cookie semantics — rejected). OAuth2 with a third-party IdP (overkill for a self-hostable single-tenant-operator product and adds an external dependency — rejected for v1).
