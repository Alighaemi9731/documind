"use client";

import { useBranding } from "@/lib/branding";
import { cn } from "@/lib/cn";

/**
 * Brand wordmark + optional same-origin logo. `app_name` is rendered as PLAIN
 * TEXT (never HTML). When a same-origin `logo_url` is configured it is shown
 * alongside the name (ARCHITECTURE.md §11).
 */
export function Logo({ className }: { className?: string }) {
  const { app_name, logo_url } = useBranding();
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      {logo_url ? (
        // Same-origin, operator-supplied logo; Next/Image optimization is not
        // needed and the standalone server does no image work (ARCHITECTURE §11).
        // eslint-disable-next-line @next/next/no-img-element
        <img src={logo_url} alt="" aria-hidden="true" className="h-6 w-6 rounded object-contain" />
      ) : null}
      <span className="text-lg font-semibold tracking-tight text-foreground">{app_name}</span>
    </span>
  );
}
