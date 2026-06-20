"use client";

/**
 * Theme (light/dark) system with NO first-paint flash.
 *
 * The authoritative `.dark` class is applied to <html> BEFORE hydration by an
 * inline {@link ThemeScript} (rendered in the root layout) that reads the
 * `documind_theme` cookie — so the server-rendered shell already carries the
 * correct class and the browser never paints the wrong theme. This provider
 * mirrors that decision into React state and persists changes back to the
 * cookie (plus the class on <html>) on toggle.
 *
 * Persistence is a cookie (not localStorage) so the value is available to the
 * pre-hydration script on the very first byte and survives reloads. "system"
 * follows the OS preference via `prefers-color-scheme`.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";

export const THEME_COOKIE = "documind_theme";

interface ThemeContextValue {
  /** The user's stored preference (light | dark | system). */
  preference: ThemePreference;
  /** The currently-applied resolved theme. */
  resolved: "light" | "dark";
  setPreference: (next: ThemePreference) => void;
  /** Convenience: cycle light → dark → light (ignores "system"). */
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

/**
 * Inline, render-blocking script that sets the `.dark` class before the first
 * paint. Kept dependency-free and tiny; emitted with the per-request CSP nonce
 * so it runs under the strict no-unsafe-inline policy.
 */
export const THEME_SCRIPT = `(function(){try{var e=document.documentElement;e.classList.add("js");var m=document.cookie.match(/(?:^|; )documind_theme=([^;]*)/);var p=m?decodeURIComponent(m[1]):"system";var d=p==="dark"||(p!=="light"&&window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches);if(d){e.classList.add("dark");}else{e.classList.remove("dark");}e.style.colorScheme=d?"dark":"light";}catch(_){}})();`;

export function ThemeScript({ nonce }: { nonce?: string }) {
  // Not dangerouslySetInnerHTML of user content — this is a static, audited
  // constant string, required to run pre-hydration to avoid a theme flash.
  return <script nonce={nonce} dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />;
}

function readCookiePreference(): ThemePreference {
  if (typeof document === "undefined") return "system";
  const m = document.cookie.match(/(?:^|; )documind_theme=([^;]*)/);
  const value = m ? decodeURIComponent(m[1]) : "system";
  return value === "light" || value === "dark" ? value : "system";
}

function systemPrefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

function resolve(pref: ThemePreference): "light" | "dark" {
  if (pref === "system") return systemPrefersDark() ? "dark" : "light";
  return pref;
}

function apply(resolved: "light" | "dark"): void {
  if (typeof document === "undefined") return;
  const el = document.documentElement;
  el.classList.toggle("dark", resolved === "dark");
  el.style.colorScheme = resolved;
}

function persist(pref: ThemePreference): void {
  if (typeof document === "undefined") return;
  // 1 year; Lax; same-origin only. Not httpOnly so the pre-hydration script can
  // read it. Contains no secret.
  document.cookie = `${THEME_COOKIE}=${pref}; path=/; max-age=31536000; SameSite=Lax`;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("light");

  // Hydrate from the cookie the pre-hydration script already honored.
  useEffect(() => {
    const pref = readCookiePreference();
    setPreferenceState(pref);
    setResolved(resolve(pref));
  }, []);

  // When following the system, react to OS theme changes live.
  useEffect(() => {
    if (preference !== "system" || typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const next = mq.matches ? "dark" : "light";
      setResolved(next);
      apply(next);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [preference]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    persist(next);
    const r = resolve(next);
    setResolved(r);
    apply(r);
  }, []);

  const toggle = useCallback(() => {
    setPreference(resolve(readCookiePreference()) === "dark" ? "light" : "dark");
  }, [setPreference]);

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, resolved, setPreference, toggle }),
    [preference, resolved, setPreference, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
