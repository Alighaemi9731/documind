import { expect, test } from "@playwright/test";

/**
 * Settings / BYOK smoke (ARCHITECTURE.md §6/§9, Phase-4 exit criteria):
 *   register -> open settings -> paste a key for a provider -> the row shows the
 *   masked "Connected" state with a fingerprint (and never the value).
 *
 * Gated by RUN_E2E=1 because it needs the full stack (web + api + postgres) in
 * `open` REGISTRATION_MODE. It is skipped (not failed) without a live stack so
 * CI stays green by default. The pasted key is a deliberately-invalid dummy;
 * the test asserts the masked connected affordance, not provider validation.
 */
const runE2E = process.env.RUN_E2E === "1";

// A throwaway, obviously-fake key. Never a real provider secret.
const DUMMY_KEY = "sk-e2e-not-a-real-key-0000000000000000";

test.describe(runE2E ? "settings (BYOK)" : "settings (skipped: set RUN_E2E=1)", () => {
  test.skip(!runE2E, "Settings e2e disabled. Set RUN_E2E=1 with a running full stack to enable.");

  test("paste a provider key and see the masked connected state", async ({ page }) => {
    const email = `e2e+settings+${Date.now()}@example.com`;
    const password = "correct-horse-battery-staple";

    // Register (open mode auto-logs in and lands on the dashboard).
    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    // Navigate to settings via the app-shell nav link.
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByRole("heading", { name: "Provider keys" })).toBeVisible();

    // Pick the first provider key row and start the paste flow. "Add key" for a
    // not-set provider; "Replace key" for one already connected (e.g. shared).
    const addButton = page.getByRole("button", { name: /Add key|Replace key/ }).first();
    await addButton.click();

    // The write-only password input appears; paste the dummy key and save.
    const keyInput = page.getByLabel(/API key/).first();
    await keyInput.fill(DUMMY_KEY);
    await page.getByRole("button", { name: "Save key" }).click();

    // After save the masked connected affordance is shown — fingerprint dots,
    // never the pasted value.
    const masked = page.getByTestId("masked-secret-connected").first();
    await expect(masked).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(DUMMY_KEY)).toHaveCount(0);
  });
});
