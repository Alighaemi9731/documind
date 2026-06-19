"use client";

import { useBranding } from "@/lib/branding";

/**
 * Client island that renders the branded app name as PLAIN TEXT. Kept tiny so
 * the landing page stays effectively static (no Framer, no data work) while
 * still reflecting the operator's branding once config loads.
 */
export function LandingBrandName() {
  const { app_name } = useBranding();
  return <>{app_name}</>;
}
