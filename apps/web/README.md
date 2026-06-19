# documind-web

The DocuMind web frontend: a Next.js 15 (App Router) + React 19 + TypeScript 5 + Tailwind CSS 3.4 application built as a standalone server (`output: "standalone"`). It listens on container-internal port `3000` and is served same-origin behind Caddy, which reverse-proxies `/api/*` to the API and everything else to this service. Use `npm run dev` for local development, `npm run build` to produce the standalone bundle, `npm run lint` / `npm run typecheck` for static checks, and `npm run test` via Playwright (set `RUN_E2E=1` with a running server) for the smoke test.

## Phase 1 — auth + tenancy

- **Auth transport (ADR-0001).** The short-lived access JWT lives only in JS memory (`lib/api.ts` module variable, surfaced via `lib/auth-context.tsx`) and is sent as `Authorization: Bearer`. On a `401`, the client performs a single-flight silent refresh against the same-origin route handler, then retries once. No token is ever stored in `localStorage`.
- **Cookie proxy.** `app/api/auth/[action]/route.ts` is the only place that touches the httpOnly refresh cookie. It proxies `POST /api/auth/refresh` and `POST /api/auth/logout` to the backend, forwarding the cookie + the `csrf_token` double-submit token (as `X-CSRF-Token`) + Origin/Referer, and relays `Set-Cookie` back to the browser.
- **Route guard.** `middleware.ts` cheaply gates `/dashboard` on the presence of the refresh cookie (authoritative check is the API via `/api/auth/me`), and keeps the CSP nonce + security headers.
- **Screens.** `/login`, `/register` (adapts to `REGISTRATION_MODE` from `GET /api/config`: open → auto-login, approval → pending state, invite → token field + `403` handling), and `/dashboard` (projects list shell over `GET`/`POST /api/projects`).

### Server-side environment

- `INTERNAL_API_URL` (default `http://api:8000`) — the backend origin the Node server reaches for the auth cookie proxy (server-to-server, inside the compose network). The browser always talks to the API same-origin via Caddy.

## Phase 5 — frontend polish + full admin dashboard

- **Design system (`components/ui/`).** A bespoke, token-driven component library (no heavy UI kit): `Button`, `Input`/`Textarea` (RTL-aware, masked-secret elsewhere), `Select`, `Card`, `Modal` (focus-trap + Esc + portal), `Toast` (+ `ToastProvider`), `Nav` (glassmorphism `backdrop-blur`, nav-only), `Tabs`, `Progress`, `Table` (responsive → stacked cards), `Skeleton`, `Badge`, `Spinner`, `ThemeToggle`, `Sparkline` (hand-rolled SVG), and a lazy `MotionDiv`. Design tokens are CSS variables in `app/globals.css` (light + `.dark`) mapped by `tailwind.config.ts`.
- **Theme.** Class-strategy dark mode persisted to the `documind_theme` cookie with **no first-paint flash** — an inline, nonce-tagged `ThemeScript` sets `.dark` before hydration (`lib/theme.tsx`).
- **RTL.** `lib/direction.ts` detects per-string fa/en direction (first-strong heuristic); CSS logical properties (`*-inline`, `ps/pe/ms/me`) throughout.
- **Branding.** `lib/branding.tsx` pulls `app_name`/`accent_color`/`logo_url` from `GET /api/config`. `app_name` renders as **plain text**; the accent is applied via the CSSOM (`document.documentElement.style.setProperty("--accent", …)`, validated, **never** an inline style attribute); only same-origin `logo_url` is honored.
- **Animation.** Framer Motion is **dynamically imported** (never in the initial/landing chunk) and only used for modal/toast/page transitions; it respects `prefers-reduced-motion` and falls back to a static `<div>`.
- **Admin (`app/(app)/admin/`).** Gated to `role === "admin"` (redirect otherwise). Sections: Users (search/filter, promote/demote/disable/delete with confirm modals + last-admin guard surfaced, per-user quota editor, per-user key fingerprints), Registrations (approval queue, shown only in approval mode, with a nav pending-count badge), Invites (create → token/link shown once, list, revoke), Usage (day/month sparklines, per-user filter), System settings (registration mode, default provider/quota, branding), and operator-key fingerprint + rotate. Typed client in `lib/admin.ts`.
- **Security.** All model/document/user text renders via the existing safe-markdown / plain text (HTML disabled, no `dangerouslySetInnerHTML` for content). `middleware.ts` sets a strict nonce CSP (`script-src 'self' 'nonce-…' 'strict-dynamic'`, no third-party CDNs, `connect-src 'self'`, self-hosted `font-src 'self'`).

### Testing & new dependencies (CI note)

- **Unit/component tests:** `npm run test` runs **Vitest** + Testing-Library (jsdom) over `tests/` — covers `Button`, `Modal` focus-trap, `Toast`, the `direction()` helper, the theme toggle/no-flash, the masked-secret input (never shows the value), and the `Sparkline`.
- **E2E:** `npm run test:e2e` runs Playwright (`RUN_E2E=1` with a running server) — including landing theme persistence, `/admin` gating, and the usage/sparkline render.
- **New deps to install in CI** (added to `package.json`): runtime `framer-motion`; dev `vitest`, `@vitejs/plugin-react`, `jsdom`, `@testing-library/{react,dom,jest-dom,user-event}`. Framer Motion is code-split and must stay out of the initial chunk (enforced by the lazy `MotionDiv`).
- **Self-hosted Persian font:** drop a Vazirmatn subset at `public/fonts/Vazirmatn-subset.woff2` (see `public/fonts/README.md`); until then the UI falls back to the system stack for Persian glyphs.
