import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { expect, test } from "@playwright/test";

/**
 * Ingestion smoke (ARCHITECTURE.md §7, Phase-2 exit criteria):
 *   register -> create a project -> open it -> upload a small fixture ->
 *   a document row appears -> poll its status pill to a terminal state.
 *
 * Gated by RUN_E2E=1 because it needs the full stack (web + api + postgres +
 * worker) in `open` REGISTRATION_MODE with a working operator Gemini key. It is
 * skipped (not failed) without a live stack so CI stays green by default.
 */
const runE2E = process.env.RUN_E2E === "1";

const FIXTURE = join(dirname(fileURLToPath(import.meta.url)), "fixtures", "sample.txt");

test.describe(runE2E ? "ingestion" : "ingestion (skipped: set RUN_E2E=1)", () => {
  test.skip(!runE2E, "Ingestion e2e disabled. Set RUN_E2E=1 with a running full stack to enable.");

  test("upload a fixture and poll a document to a terminal state", async ({ page }) => {
    const email = `e2e+ingest+${Date.now()}@example.com`;
    const password = "correct-horse-battery-staple";

    // Register (open mode auto-logs in and lands on the dashboard).
    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    // Create a project.
    const projectName = `Ingest ${Date.now()}`;
    await page.getByRole("button", { name: "New project" }).click();
    await page.getByLabel("Name").fill(projectName);
    await page.getByRole("button", { name: "Create" }).click();

    // Open the project view via the dashboard link.
    await page.getByRole("link", { name: projectName }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

    // Upload the fixture through the hidden file input behind the dropzone.
    await page.getByLabel("Choose files to upload").setInputFiles(FIXTURE);
    await expect(page.getByText("sample.txt")).toBeVisible();
    await page.getByRole("button", { name: /Upload \d+ file/ }).click();

    // The document row appears in the list (filename rendered).
    const docRow = page.getByText("sample.txt").last();
    await expect(docRow).toBeVisible();

    // Poll the status pill to a terminal state. The hook polls ~2s; allow ample
    // time for parse -> chunk -> embed -> store. A terminal state is Ready or
    // Failed; the happy path is Ready, but we accept Failed so an environment
    // without a Gemini key still proves the state machine reaches terminal.
    const terminalPill = page.getByRole("status").filter({ hasText: /Ready|Failed/ });
    await expect(terminalPill.first()).toBeVisible({ timeout: 90_000 });
  });
});
