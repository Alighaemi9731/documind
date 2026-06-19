import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Force the static (non-Framer) render path in component tests so the lazy
// framer-motion chunk is never resolved under jsdom (deterministic + fast).
process.env.NEXT_PUBLIC_DISABLE_MOTION = "1";

// jsdom lacks matchMedia; provide a benign stub (defaults to light / no reduce).
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

afterEach(() => {
  cleanup();
});
