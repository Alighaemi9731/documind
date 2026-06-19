import { cn } from "@/lib/cn";

export interface ProgressProps {
  /** 0..1 fractional progress. */
  value: number;
  /** Accessible label for the bar. */
  label?: string;
  className?: string;
  /** Minimum visible fill (so the bar is never fully empty) as a fraction. */
  minVisible?: number;
}

/** Accessible determinate progress bar; width is driven by a class-safe inline. */
export function Progress({ value, label, className, minVisible = 0.06 }: ProgressProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const pct = Math.round(clamped * 100);
  const width = `${Math.max(clamped, minVisible) * 100}%`;
  return (
    <div
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-label={label}
    >
      <div
        className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
        // Width is a numeric, sanitized value (clamped 0..100%); it carries no
        // user text and cannot break the CSP (style attr is allowed; scripts are
        // not — see middleware).
        style={{ width }}
      />
    </div>
  );
}
