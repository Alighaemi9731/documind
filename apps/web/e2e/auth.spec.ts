import { expect, test } from "@playwright/test";

/**
 * Auth flow smoke: register -> dashboard -> reload (silent refresh keeps the
 * session) -> logout.
 *
 * Gated by RUN_E2E=1 because it requires a fully running stack (web + api +
 * postgres) in `open` REGISTRATION_MODE. Skipped in CI without a live stack.
 */
const runE2E = process.env.RUN_E2E === "1";

test.describe(runE2E ? "auth flow" : "auth flow (skipped: set RUN_E2E=1)", () => {
  test.skip(!runE2E, "Auth e2e disabled. Set RUN_E2E=1 with a running full stack to enable.");

  test("register, persist across reload, and logout", async ({ page }) => {
    const email = `e2e+${Date.now()}@example.com`;
    const password = "correct-horse-battery-staple";

    // Register (open mode auto-logs in and lands on the dashboard).
    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();

    // Reload: the in-memory access token is lost but the httpOnly refresh
    // cookie drives a silent refresh that keeps us authenticated.
    await page.reload();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();

    // Logout clears the session and returns to /login.
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login(\?.*)?$/);

    // The protected route is now gated by the middleware (no refresh cookie).
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login(\?.*)?$/);
  });
});
