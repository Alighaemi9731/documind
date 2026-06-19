import { describe, expect, it } from "vitest";

import { direction, hasRtlRun, isRtl } from "@/lib/direction";

describe("direction()", () => {
  it("detects an English run as ltr", () => {
    expect(direction("Hello world")).toBe("ltr");
    expect(isRtl("Hello world")).toBe(false);
  });

  it("detects a Persian run as rtl", () => {
    expect(direction("سلام دنیا")).toBe("rtl");
    expect(isRtl("سلام دنیا")).toBe(true);
  });

  it("detects an Arabic run as rtl", () => {
    expect(direction("مرحبا بالعالم")).toBe("rtl");
  });

  it("uses the FIRST strong character for mixed content", () => {
    // First strong char is Latin → ltr even though Persian follows.
    expect(direction("Invoice فاکتور")).toBe("ltr");
    // First strong char is Persian → rtl even though English follows.
    expect(direction("فاکتور Invoice")).toBe("rtl");
  });

  it("returns auto for digits/punctuation/empty (no strong char)", () => {
    expect(direction("12345")).toBe("auto");
    expect(direction("  -- !! ")).toBe("auto");
    expect(direction("")).toBe("auto");
    expect(direction(null)).toBe("auto");
    expect(direction(undefined)).toBe("auto");
  });

  it("hasRtlRun finds any RTL run regardless of position", () => {
    expect(hasRtlRun("Report فصل 2")).toBe(true);
    expect(hasRtlRun("Report chapter 2")).toBe(false);
  });
});
