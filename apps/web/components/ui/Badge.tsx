import { cn } from "@/lib/cn";

type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  /** Shows a leading dot (e.g. a live/animated status indicator). */
  dot?: boolean;
  /** Animate the dot (for non-terminal/active states). */
  pulse?: boolean;
}

const TONES: Record<Tone, string> = {
  neutral: "bg-muted text-muted-foreground border-border",
  accent: "bg-accent/10 text-accent border-accent/30",
  success: "bg-success/10 text-success border-success/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  danger: "bg-danger/10 text-danger border-danger/30",
  info: "bg-blue-500/10 text-blue-600 border-blue-500/30 dark:text-blue-400",
};

/** Small pill/badge for labels, counts, and status. */
export function Badge({
  tone = "neutral",
  dot = false,
  pulse = false,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
      {...props}
    >
      {dot ? (
        <span
          className={cn("h-1.5 w-1.5 rounded-full bg-current", pulse && "animate-pulse")}
          aria-hidden="true"
        />
      ) : null}
      {children}
    </span>
  );
}
