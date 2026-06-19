import { test, expect } from "@playwright/test";

/**
 * Admin-gating smoke (ARCHITECTURE.md §10): a non-admin (or unauthenticated)
 * visitor to /admin is redirected away from the dashboard rather than seeing it.
 * Set RUN_E2E=1 to enable against a running stack.
 */
const runE2E = process.env.RUN_E2E === "1";

test.describe(runE2E ? "admin gating" : "admin gating (skipped: set RUN_E2E=1)", () => {
  test.skip(!runE2E, "Smoke e2e disabled. Set RUN_E2E=1 with a running web server to enable.");

  test("unauthenticated visit to /admin redirects to login", async ({ page }) => {
    await page.goto("/admin");
    await page.waitForURL(/\/login/);
    await expect(page).toHaveURL(/\/login/);
  });
});
