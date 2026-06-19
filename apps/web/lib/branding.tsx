"use client";

/**
 * Runtime branding (app_name, accent_color, logo_url) from GET /api/config
 * (ARCHITECTURE.md §11).
 *
 * SECURITY:
 *  - `app_name` is rendered as PLAIN TEXT everywhere (nav/landing/title) — never
 *    as HTML.
 *  - `accent_color` is applied with the CSSOM API
 *    (`document.documentElement.style.setProperty("--accent", …)`), NOT an
 *    inline `style` attribute, so the strict no-`unsafe-inline` CSP holds. The
 *    value is validated against a strict color allow-list before it is applied
 *    (defends against a malicious admin injecting CSS).
 *  - `logo_url` is only honored when it is a same-origin relative path.
 */

import { createContext, useContext, useEffect, useState } from "react";

import { getAppConfig } from "./config";
import type { Branding } from "./types";

export const DEFAULT_BRANDING: Branding = {
  app_name: "DocuMind",
  accent_color: "",
  logo_url: null,
};

/**
 * Validate an accent color: only `#rgb`/`#rrggbb` hex or a Tailwind-style HSL
 * triple ("221 83% 53%") are allowed. Anything else (functions, url(), etc.) is
 * rejected so it can never break out of the custom-property value.
 */
export function normalizeAccent(color: string | null | undefined): string | null {
  if (!color) return null;
  const trimmed = color.trim();
  if (/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(trimmed)) {
    return trimmed;
  }
  // Bare HSL channels like "221 83% 53%" (consumed by hsl(var(--accent))).
  if (/^\d{1,3}\s+\d{1,3}%\s+\d{1,3}%$/.test(trimmed)) {
    return trimmed;
  }
  return null;
}

/** Only same-origin, relative logo paths are honored (no off-origin fetch). */
export function safeLogoUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (trimmed.startsWith("/") && !trimmed.startsWith("//")) {
    return trimmed;
  }
  return null;
}

/**
 * Apply the accent color via the CSSOM (never an inline style attribute, so the
 * strict no-`unsafe-inline` CSP holds). Tailwind's `accent` utilities resolve to
 * `hsl(var(--accent))`, so `--accent` must hold "H S% L%" channels: a hex value
 * is converted to those channels first, an HSL-triple is used as-is.
 */
export function applyAccent(color: string | null): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const normalized = normalizeAccent(color);
  if (!normalized) {
    root.style.removeProperty("--accent");
    return;
  }
  const channels = normalized.startsWith("#") ? channelsFromHex(normalized) : normalized;
  root.style.setProperty("--accent", channels);
}

/** Convert `#rrggbb`/`#rgb` to "H S% L%" channels for the --accent variable. */
function channelsFromHex(hex: string): string {
  let r = 0;
  let g = 0;
  let b = 0;
  if (hex.length === 4) {
    r = parseInt(hex[1] + hex[1], 16);
    g = parseInt(hex[2] + hex[2], 16);
    b = parseInt(hex[3] + hex[3], 16);
  } else {
    r = parseInt(hex.slice(1, 3), 16);
    g = parseInt(hex.slice(3, 5), 16);
    b = parseInt(hex.slice(5, 7), 16);
  }
  const rn = r / 255;
  const gn = g / 255;
  const bn = b / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  const d = max - min;
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === rn) h = (gn - bn) / d + (gn < bn ? 6 : 0);
    else if (max === gn) h = (bn - rn) / d + 2;
    else h = (rn - gn) / d + 4;
    h /= 6;
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

const BrandingContext = createContext<Branding>(DEFAULT_BRANDING);

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);

  useEffect(() => {
    let active = true;
    getAppConfig()
      .then((config) => {
        if (!active || !config.branding) return;
        const next: Branding = {
          app_name: config.branding.app_name || DEFAULT_BRANDING.app_name,
          accent_color: config.branding.accent_color ?? "",
          logo_url: safeLogoUrl(config.branding.logo_url),
        };
        setBranding(next);
        applyAccent(next.accent_color);
        if (typeof document !== "undefined" && next.app_name) {
          document.title = next.app_name;
        }
      })
      .catch(() => {
        // Keep defaults on failure (offline / not-yet-seeded install).
      });
    return () => {
      active = false;
    };
  }, []);

  return <BrandingContext.Provider value={branding}>{children}</BrandingContext.Provider>;
}

export function useBranding(): Branding {
  return useContext(BrandingContext);
}
