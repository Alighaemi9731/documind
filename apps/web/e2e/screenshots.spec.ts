import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { expect, test } from "@playwright/test";

/**
 * Screenshot generator for the README (docs/screenshots/). NOT an assertion
 * suite — it navigates the app and saves PNGs. The public landing shots need
 * only the web server; the authenticated shots additionally need the full stack
 * and are best-effort (wrapped so a missing page/selector skips that shot rather
 * than failing the run). Gated by RUN_E2E=1 like the other e2e specs.
 *
 *   RUN_E2E=1 PLAYWRIGHT_BASE_URL=http://localhost:3000 \
 *     npx playwright test e2e/screenshots.spec.ts
 */
const runE2E = process.env.RUN_E2E === "1";
const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "docs", "screenshots");

test.describe(runE2E ? "screenshots" : "screenshots (skipped: set RUN_E2E=1)", () => {
  test.skip(!runE2E, "Screenshot capture disabled. Set RUN_E2E=1 with a running stack.");
  test.use({ viewport: { width: 1280, height: 800 } });

  test("capture marketing + app screenshots", async ({ page, context }) => {
    // --- Landing, light ---
    await page.goto("/");
    await page.waitForLoadState("networkidle").catch(() => {});
    await page.screenshot({ path: join(OUT, "landing-light.png"), fullPage: true });

    // --- Landing, dark (cookie-backed, applied pre-hydration → no flash) ---
    await context.addCookies([{ name: "documind_theme", value: "dark", url: page.url() }]);
    await page.reload();
    await expect(page.locator("html.dark"))
      .toBeVisible()
      .catch(() => {});
    await page.screenshot({ path: join(OUT, "landing-dark.png"), fullPage: true });

    // --- Landing, RTL (force document direction for the layout shot) ---
    await context.addCookies([{ name: "documind_theme", value: "light", url: page.url() }]);
    await page.addInitScript(() => document.documentElement.setAttribute("dir", "rtl"));
    await page.reload();
    await page.screenshot({ path: join(OUT, "landing-rtl.png"), fullPage: true });
    await page.addInitScript(() => document.documentElement.setAttribute("dir", "ltr"));

    // --- Authenticated shots (best-effort; need the full stack) ---
    const email = `e2e+shot+${Date.now()}@example.com`;
    const password = "correct-horse-battery-staple";
    const shoot = async (name: string, fn: () => Promise<void>) => {
      try {
        await fn();
        await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
      } catch {
        // Live data unavailable — skip this shot, keep the run green.
      }
    };

    await shoot("dashboard", async () => {
      await page.goto("/register");
      await page.getByLabel("Email").fill(email);
      await page.getByLabel("Password").fill(password);
      await page.getByRole("button", { name: "Create account" }).click();
      await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15000 });
    });

    await shoot("admin", async () => {
      await page.goto("/admin");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 10000 });
    });
  });
});
