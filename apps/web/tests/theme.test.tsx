import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { THEME_SCRIPT, ThemeProvider } from "@/lib/theme";

function setCookie(value: string) {
  document.cookie = `documind_theme=${value}; path=/`;
}

describe("theme system", () => {
  beforeEach(() => {
    document.documentElement.className = "";
    setCookie("");
  });

  afterEach(() => {
    document.documentElement.className = "";
  });

  it("the no-flash script applies .dark from the cookie before hydration", () => {
    setCookie("dark");
    // Execute the inline pre-hydration script the way the browser would.
    // eslint-disable-next-line no-new-func
    new Function(THEME_SCRIPT)();
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    setCookie("light");
    // eslint-disable-next-line no-new-func
    new Function(THEME_SCRIPT)();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("toggling persists the preference to the cookie and flips the class", async () => {
    setCookie("light");
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const toggle = screen.getByTestId("theme-toggle");
    await userEvent.click(toggle);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.cookie).toContain("documind_theme=dark");

    await userEvent.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.cookie).toContain("documind_theme=light");
  });
});
