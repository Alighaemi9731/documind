import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sparkline } from "@/components/ui/Sparkline";

describe("Sparkline", () => {
  it("renders an accessible svg with a path for a multi-point series", () => {
    render(<Sparkline values={[1, 4, 2, 8, 5]} label="tokens trend" />);
    const svg = screen.getByTestId("sparkline");
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg).toHaveAttribute("aria-label", "tokens trend");
    const path = svg.querySelector("path[stroke]");
    expect(path).not.toBeNull();
    expect(path?.getAttribute("d")).toMatch(/^M /);
  });

  it("draws a flat baseline for an empty series without throwing", () => {
    render(<Sparkline values={[]} label="empty" />);
    const svg = screen.getByTestId("sparkline");
    const path = svg.querySelector("path[stroke]");
    expect(path?.getAttribute("d")).toContain("L");
  });

  it("handles a single-point series", () => {
    render(<Sparkline values={[42]} label="single" />);
    const svg = screen.getByTestId("sparkline");
    expect(svg.querySelector("path[stroke]")).not.toBeNull();
  });
});
