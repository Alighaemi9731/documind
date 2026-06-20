import { cn } from "@/lib/cn";

/**
 * Hero centerpiece: a faux chat window that animates a real grounded, cited
 * answer streaming in (CSS-only, plays once on load; disabled under
 * prefers-reduced-motion). Decorative — aria-hidden. Token-driven, so it tracks
 * light/dark + the operator branding accent.
 */
export function ChatDemo({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "floaty relative w-full max-w-lg rounded-2xl border border-border/70 bg-card/80 shadow-2xl shadow-black/10 backdrop-blur-xl",
        className,
      )}
    >
      {/* window chrome */}
      <div className="flex items-center gap-2 border-b border-border/60 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-[hsl(0_70%_62%)]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[hsl(40_80%_58%)]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[hsl(140_50%_50%)]" />
        <span className="ms-2 text-xs font-medium text-muted-foreground">
          DocuMind · handbook.pdf
        </span>
        <span className="ms-auto inline-flex items-center gap-1 rounded-full bg-[hsl(140_55%_45%)]/12 px-2 py-0.5 text-[10px] font-semibold text-[hsl(142_60%_40%)] dark:text-[hsl(142_55%_62%)]">
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          Grounded
        </span>
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        {/* user question */}
        <div className="flex justify-end">
          <p className="max-w-[80%] rounded-2xl rounded-ee-sm bg-accent px-3.5 py-2 text-sm text-accent-foreground shadow-sm">
            What’s our refund window for annual plans?
          </p>
        </div>

        {/* assistant answer */}
        <div className="flex justify-start">
          <div className="max-w-[88%] rounded-2xl rounded-es-sm border border-border bg-background/70 px-3.5 py-3 text-sm leading-relaxed">
            <p className="demo-line text-foreground">
              Annual plans can be refunded in full within{" "}
              <span className="font-semibold">30 days</span> of purchase.
            </p>
            <p className="demo-line mt-1.5 text-foreground">
              After 30 days they’re prorated to the unused months
              <span className="demo-caret" />
            </p>
            <p className="demo-line mt-1.5 text-muted-foreground">
              — refunds are issued to the original payment method.
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="demo-chip inline-flex items-center gap-1 rounded-md bg-accent/10 px-1.5 py-0.5 text-xs font-medium text-accent ring-1 ring-inset ring-accent/20">
                <CiteIcon /> handbook.pdf · p.12
              </span>
              <span className="demo-chip inline-flex items-center gap-1 rounded-md bg-accent/10 px-1.5 py-0.5 text-xs font-medium text-accent ring-1 ring-inset ring-accent/20">
                <CiteIcon /> handbook.pdf · p.13
              </span>
            </div>
          </div>
        </div>

        {/* thinking shimmer that the lines "replace" */}
        <div className="demo-src flex items-center gap-2 ps-1 text-xs text-muted-foreground">
          <span className="demo-typing inline-flex gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
          </span>
          retrieved 4 passages · answered from your document
        </div>
      </div>
    </div>
  );
}

function CiteIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M7 8h10M7 12h7M6 4h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-4 3V6a2 2 0 0 1 2-2z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
