# Screenshots

These images are referenced from the top-level [README](../../README.md). They
are **generated**, not hand-curated, so they stay current with the UI.

## Regenerate

From a running stack (web on `http://localhost:3000`, full API + a working
operator Gemini key so a document can be ingested and answered):

```bash
cd apps/web
RUN_E2E=1 PLAYWRIGHT_BASE_URL=http://localhost:3000 \
  npx playwright test e2e/screenshots.spec.ts
```

The spec writes PNGs into this directory:

| File | What |
| --- | --- |
| `landing-light.png` | Marketing landing page, light theme |
| `landing-dark.png` | Marketing landing page, dark theme |
| `landing-rtl.png` | Landing page in RTL (Persian) layout |
| `dashboard.png` | Signed-in dashboard with a project |
| `project-chat.png` | Project Q&A — a grounded answer with citation chips |
| `admin.png` | Admin dashboard (users / usage / settings) |

The public landing shots (`landing-*`) need only the web server; the
authenticated shots additionally need the API + Postgres + worker (the spec
registers a throwaway user and creates a project). Each authenticated capture is
best-effort and is skipped silently if the live data isn't available, so the
spec never fails a CI run — it only produces whatever it can.

Binary PNGs are intentionally not committed by default (keeps the repo lean);
generate them locally or in a docs pipeline when publishing.
