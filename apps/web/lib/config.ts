/**
 * Public app config loader (GET /api/config).
 *
 * Surfaces `{max_upload_mb, registration_mode}` so the auth UI can adapt to the
 * operator's REGISTRATION_MODE (open / approval / invite) without baking it in
 * at build time. Cached for the lifetime of the page (config rarely changes).
 */

import { apiPublicFetch } from "./api";
import type { AppConfig } from "./types";

let cached: Promise<AppConfig> | null = null;

export function getAppConfig(): Promise<AppConfig> {
  if (!cached) {
    cached = apiPublicFetch<AppConfig>("/config").catch((err) => {
      // Allow a later retry if the first load failed.
      cached = null;
      throw err;
    });
  }
  return cached;
}
