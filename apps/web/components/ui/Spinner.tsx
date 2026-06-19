import { cn } from "@/lib/cn";

export interface SpinnerProps {
  /** Diameter token. */
  size?: "sm" | "md" | "lg";
  className?: string;
  /** Accessible label (visually hidden). */
  label?: string;
}

const SIZES: Record<NonNullable<SpinnerProps["size"]>, string> = {
  sm: "h-4 w-4 border-2",
  md: "h-5 w-5 border-2",
  lg: "h-7 w-7 border-[3px]",
};

/** A simple, dependency-free CSS spinner (respects prefers-reduced-motion). */
export function Spinner({ size = "md", className, label }: SpinnerProps) {
  return (
    <span role="status" className="inline-flex items-center">
      <span
        className={cn(
          "animate-spin rounded-full border-current border-t-transparent",
          SIZES[size],
          className,
        )}
        aria-hidden="true"
      />
      <span className="sr-only">{label ?? "Loading"}</span>
    </span>
  );
}
