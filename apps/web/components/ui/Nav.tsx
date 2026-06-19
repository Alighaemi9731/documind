import { cn } from "@/lib/cn";

/**
 * Glassmorphism nav shell (the ONLY surface using backdrop-blur, per §11).
 * Sticky, translucent, hairline bottom border. Content (logo, links, actions)
 * is provided by the caller.
 */
export function Nav({ className, children, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b border-border/70",
        "bg-glass/70 backdrop-blur-xl supports-[backdrop-filter]:bg-glass/60",
        className,
      )}
      {...props}
    >
      <div className="mx-auto flex h-16 w-full max-w-8xl items-center justify-between gap-4 px-4 sm:px-6">
        {children}
      </div>
    </header>
  );
}
