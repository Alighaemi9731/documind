/**
 * Per-string text-direction detection for mixed Persian/Arabic + English (fa/en)
 * content (ARCHITECTURE.md §11).
 *
 * The whole UI sets `dir` from the active language, but individual user/content
 * strings (a Persian project name, an English filename) may not match the chrome
 * direction. {@link direction} inspects the FIRST strong directional character —
 * the same heuristic the Unicode bidi "first strong" rule uses — so each run
 * renders correctly without a heavy bidi library.
 */

/** RTL scripts we care about: Arabic, Persian, Hebrew, plus Arabic forms. */
const RTL_RANGE = /[֑-߿ࡠ-ࣿיִ-﷿ﹰ-﻿\u{10800}-\u{10FFF}]/u;

/** A "strong" LTR character (basic Latin letters and common Latin extensions). */
const LTR_RANGE = /[A-Za-zÀ-ʯͰ-֏]/;

/**
 * Resolve the writing direction of `text` by its first strong character.
 * Returns "rtl" when the first strong char is RTL, "ltr" when it is LTR, and
 * "auto" when the string has no strong character (digits/punctuation/empty) so
 * the browser can decide.
 */
export function direction(text: string | null | undefined): "rtl" | "ltr" | "auto" {
  if (!text) return "auto";
  for (const ch of text) {
    if (RTL_RANGE.test(ch)) return "rtl";
    if (LTR_RANGE.test(ch)) return "ltr";
  }
  return "auto";
}

/** True when the string's dominant (first-strong) direction is RTL. */
export function isRtl(text: string | null | undefined): boolean {
  return direction(text) === "rtl";
}

/** True when the string contains any Persian/Arabic/Hebrew run. */
export function hasRtlRun(text: string | null | undefined): boolean {
  return !!text && RTL_RANGE.test(text);
}
