# documind-web

The DocuMind web frontend: a Next.js 15 (App Router) + React 19 + TypeScript 5 + Tailwind CSS 3.4 application built as a standalone server (`output: "standalone"`). It listens on container-internal port `3000` and is served same-origin behind Caddy, which reverse-proxies `/api/*` to the API and everything else to this service. Use `npm run dev` for local development, `npm run build` to produce the standalone bundle, `npm run lint` / `npm run typecheck` for static checks, and `npm run test` via Playwright (set `RUN_E2E=1` with a running server) for the smoke test.

## Phase 1 — auth + tenancy

- **Auth transport (ADR-0001).** The short-lived access JWT lives only in JS memory (`lib/api.ts` module variable, surfaced via `lib/auth-context.tsx`) and is sent as `Authorization: Bearer`. On a `401`, the client performs a single-flight silent refresh against the same-origin route handler, then retries once. No token is ever stored in `localStorage`.
- **Cookie proxy.** `app/api/auth/[action]/route.ts` is the only place that touches the httpOnly refresh cookie. It proxies `POST /api/auth/refresh` and `POST /api/auth/logout` to the backend, forwarding the cookie + the `csrf_token` double-submit token (as `X-CSRF-Token`) + Origin/Referer, and relays `Set-Cookie` back to the browser.
- **Route guard.** `middleware.ts` cheaply gates `/dashboard` on the presence of the refresh cookie (authoritative check is the API via `/api/auth/me`), and keeps the CSP nonce + security headers.
- **Screens.** `/login`, `/register` (adapts to `REGISTRATION_MODE` from `GET /api/config`: open → auto-login, approval → pending state, invite → token field + `403` handling), and `/dashboard` (projects list shell over `GET`/`POST /api/projects`).

### Server-side environment

- `INTERNAL_API_URL` (default `http://api:8000`) — the backend origin the Node server reaches for the auth cookie proxy (server-to-server, inside the compose network). The browser always talks to the API same-origin via Caddy.
