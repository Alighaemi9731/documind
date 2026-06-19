import { test, expect } from "@playwright/test";

/**
 * Smoke test for the static landing shell.
 *
 * Set RUN_E2E=1 to enable; otherwise CI can skip when no server is running.
 */
const runE2E = process.env.RUN_E2E === "1";

test.describe(runE2E ? "landing shell" : "landing shell (skipped: set RUN_E2E=1)", () => {
  test.skip(!runE2E, "Smoke e2e disabled. Set RUN_E2E=1 with a running web server to enable.");

  test("loads the home page and shows the product name", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toContainText("DocuMind");
  });
});
