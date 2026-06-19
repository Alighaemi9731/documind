import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { expect, test } from "@playwright/test";

/**
 * Chat Q&A smoke (ARCHITECTURE.md §8, Phase-3 exit criteria):
 *   register -> create a project -> upload a fixture -> wait for it to be Ready
 *   -> open the Chat tab -> ask a question -> assistant tokens stream in ->
 *   the answer settles into EITHER a grounded answer with >=1 citation chip OR
 *   the guarded "Not in your documents" state.
 *
 * Gated by RUN_E2E=1 because it needs the full stack (web + api + postgres +
 * worker) in `open` REGISTRATION_MODE with a working operator Gemini key (for
 * embeddings + chat). Skipped (not failed) without a live stack so CI stays
 * green by default. Either terminal outcome is a pass: a stack without a chat
 * key, or a question the corpus can't support, legitimately lands on the
 * guarded refusal — both prove the streamed contract end to end.
 */
const runE2E = process.env.RUN_E2E === "1";

const FIXTURE = join(dirname(fileURLToPath(import.meta.url)), "fixtures", "sample.txt");

test.describe(runE2E ? "chat" : "chat (skipped: set RUN_E2E=1)", () => {
  test.skip(!runE2E, "Chat e2e disabled. Set RUN_E2E=1 with a running full stack to enable.");

  test("ask a question and stream a grounded answer or the guarded state", async ({ page }) => {
    const email = `e2e+chat+${Date.now()}@example.com`;
    const password = "correct-horse-battery-staple";

    // Register (open mode auto-logs in and lands on the dashboard).
    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    // Create a project and open it.
    const projectName = `Chat ${Date.now()}`;
    await page.getByRole("button", { name: "New project" }).click();
    await page.getByLabel("Name").fill(projectName);
    await page.getByRole("button", { name: "Create" }).click();
    await page.getByRole("link", { name: projectName }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

    // Upload a fixture and wait for it to become Ready so retrieval has content.
    await page.getByLabel("Choose files to upload").setInputFiles(FIXTURE);
    await page.getByRole("button", { name: /Upload \d+ file/ }).click();
    const readyPill = page.getByRole("status").filter({ hasText: "Ready" });
    await expect(readyPill.first()).toBeVisible({ timeout: 90_000 });

    // Switch to the Chat tab and ask a question.
    await page.getByRole("tab", { name: "Chat" }).click();
    const composer = page.getByLabel("Ask a question about your documents");
    await composer.fill("What is this document about?");
    await page.getByRole("button", { name: "Send" }).click();

    // The user turn is echoed immediately.
    await expect(page.locator('[data-role="user"]').last()).toContainText(
      "What is this document about?",
    );

    // The assistant turn settles into one of two terminal shapes:
    //   - grounded answer: at least one citation chip is rendered, OR
    //   - guarded refusal: the "Not in your documents" note is shown.
    const citationChip = page.getByLabel(/^Source 1:/);
    const guarded = page.getByText("Not in your documents");
    await expect(citationChip.first().or(guarded.first())).toBeVisible({ timeout: 60_000 });

    // The Send button returns (streaming finished) — the Stop button is gone.
    await expect(page.getByRole("button", { name: "Send" })).toBeVisible({ timeout: 60_000 });
  });
});
