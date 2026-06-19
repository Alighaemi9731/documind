# ADR-0012: Frontend footprint — Next.js standalone, no SSR fetch, TanStack Query, polling, bespoke components

- Status: Accepted
- Date: 2026-06-19
- Deciders: DocuMind lead engineer

## Context
The web tier runs in its own container (`web:3000`) on the same small VPS as the API and Postgres, behind Caddy on the same origin (ADR-0011). It must produce a small, self-contained runtime image, must not duplicate auth/data logic on the server (auth is in-memory bearer + httpOnly refresh per ADR-0001, which the SSR server does not hold), and must keep client memory and bundle size modest. Ingestion is asynchronous (ADR-0005), so the UI needs a way to reflect job status.

## Decision
Build the frontend on **Next.js 15 (App Router) + React 19 + TypeScript 5 + Tailwind CSS 3.4**, with `next.config` set to **`output: 'standalone'`** for a minimal, dependency-traced runtime image. **No SSR data fetching** — in Phase 0 the server renders only a static shell; all authenticated data is fetched **client-side from the FastAPI backend via TanStack Query** (the client holds the in-memory access token, the SSR server does not). Ingestion status is surfaced by **polling** the API, **not SSE/WebSockets**. The component library is **bespoke** (no heavy third-party UI kit).

## Consequences
`output: 'standalone'` yields a small container that ships only what is used, fitting the memory-constrained host. Keeping all data fetching client-side means the SSR layer never needs the user's credentials, which aligns cleanly with the in-memory-bearer auth model (ADR-0001) and avoids token-handling duplication on the Node server. TanStack Query gives caching, retries, and request dedup for free. Polling is simpler and more robust behind a reverse proxy than long-lived SSE/WebSocket connections, and ingestion is not latency-critical. A bespoke component set keeps the bundle lean and avoids a large UI-kit dependency. Costs: no SSR data fetch means no server-rendered initial content for authenticated views (a first paint then a client fetch); polling is less instantaneous and slightly chattier than push; a bespoke component library is more upfront work than adopting an off-the-shelf kit.

## Alternatives considered
SSR/RSC data fetching with the user's session (requires the SSR server to hold credentials, conflicting with ADR-0001 — rejected). SSE or WebSockets for ingestion status (more fragile through Caddy, more server state, unnecessary for non-real-time status — rejected, polling chosen). A heavy UI component kit (MUI/AntD) (large bundle, heavier runtime — rejected for the small-host target).
