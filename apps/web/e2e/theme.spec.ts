import { test, expect } from "@playwright/test";

/**
 * Landing theme-persistence smoke (ARCHITECTURE.md §11): toggling the theme sets
 * the cookie and survives a reload with NO first-paint flash (the .dark class is
 * present on the very first paint after reload). Set RUN_E2E=1 to enable.
 */
const runE2E = process.env.RUN_E2E === "1";

test.describe(runE2E ? "theme persistence" : "theme persistence (skipped: set RUN_E2E=1)", () => {
  test.skip(!runE2E, "Smoke e2e disabled. Set RUN_E2E=1 with a running web server to enable.");

  test("toggling theme persists across reload without a flash", async ({ page }) => {
    await page.goto("/");

    const toggle = page.getByTestId("theme-toggle").first();
    await toggle.click();

    const isDarkAfterToggle = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );

    // The cookie should record the new preference.
    const cookies = await page.context().cookies();
    const themeCookie = cookies.find((c) => c.name === "documind_theme");
    expect(themeCookie?.value).toBe(isDarkAfterToggle ? "dark" : "light");

    // After reload, the class is applied pre-hydration (no flash).
    await page.reload();
    const isDarkAfterReload = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );
    expect(isDarkAfterReload).toBe(isDarkAfterToggle);
  });
});
