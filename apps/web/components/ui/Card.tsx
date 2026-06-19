import { cn } from "@/lib/cn";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Adds hover elevation + cursor affordance (for clickable cards/links). */
  interactive?: boolean;
  /** Surface elevation. */
  elevation?: "flat" | "sm" | "md";
}

const ELEVATION = {
  flat: "shadow-none",
  sm: "shadow-sm",
  md: "shadow-md",
} as const;

/** Layered-shadow, large-radius surface — the primary content container. */
export function Card({
  interactive = false,
  elevation = "sm",
  className,
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-card text-card-foreground",
        ELEVATION[elevation],
        interactive &&
          "transition-[box-shadow,transform,background-color] duration-150 hover:-translate-y-0.5 hover:shadow-md focus-within:shadow-md",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-6 pb-0", className)} {...props} />;
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-base font-semibold tracking-tight text-card-foreground", className)}
      {...props}
    />
  );
}
