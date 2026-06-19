import { cn } from "@/lib/cn";
import type { DocumentErrorCode, DocumentStatus } from "@/lib/types";

/**
 * Accessible status pill for a document's ingestion stage (ADR-0013 enum).
 *
 * Color is paired with a text label (never color-alone, for color-blind/AX
 * users). Non-terminal stages animate a small dot; `failed` surfaces the typed
 * `error_code` reason. The state-machine order is queued → parsing → chunking →
 * embedding → ready, with any stage able to fall to `failed`.
 */

/** Stage ordering for per-stage progress (terminal `ready` is the 1.0 anchor). */
export const STATUS_STAGES: DocumentStatus[] = [
  "queued",
  "parsing",
  "chunking",
  "embedding",
  "ready",
];

const TERMINAL: ReadonlySet<DocumentStatus> = new Set(["ready", "failed"]);

export function isTerminalStatus(status: DocumentStatus): boolean {
  return TERMINAL.has(status);
}

/**
 * Fractional progress (0..1) for a status, used by the per-stage progress bar.
 * `queued` shows a sliver so the bar is never empty; `failed` reports 0.
 */
export function statusProgress(status: DocumentStatus): number {
  if (status === "failed") return 0;
  const idx = STATUS_STAGES.indexOf(status);
  if (idx < 0) return 0;
  return idx / (STATUS_STAGES.length - 1);
}

const LABELS: Record<DocumentStatus, string> = {
  queued: "Queued",
  parsing: "Parsing",
  chunking: "Chunking",
  embedding: "Embedding",
  ready: "Ready",
  failed: "Failed",
};

const STYLES: Record<DocumentStatus, string> = {
  queued: "bg-muted text-muted-foreground border-border",
  parsing: "bg-blue-500/10 text-blue-600 border-blue-500/30 dark:text-blue-400",
  chunking: "bg-blue-500/10 text-blue-600 border-blue-500/30 dark:text-blue-400",
  embedding: "bg-blue-500/10 text-blue-600 border-blue-500/30 dark:text-blue-400",
  ready: "bg-green-500/10 text-green-700 border-green-500/30 dark:text-green-400",
  failed: "bg-red-500/10 text-red-600 border-red-500/40 dark:text-red-400",
};

/** Human-readable reasons for each typed error code (ADR-0013). */
const ERROR_REASONS: Record<DocumentErrorCode, string> = {
  OVERSIZE: "File exceeds the upload size limit.",
  BAD_TYPE: "Unsupported file type.",
  DECOMPRESSION_BOMB: "File rejected as a potential decompression bomb.",
  ENCRYPTED_PDF: "PDF is encrypted and cannot be read.",
  NO_TEXT: "No extractable text (image-only PDFs are not supported).",
  PARSE_ERROR: "The file could not be parsed.",
  EMBED_ERROR: "Embedding failed. Try reprocessing.",
  TOO_MANY_CHUNKS: "Document is too large (too many chunks).",
};

export function statusLabel(status: DocumentStatus): string {
  return LABELS[status];
}

/** Maps an error code (typed or unknown string) to a human reason. */
export function errorReason(code?: DocumentErrorCode | string | null): string | null {
  if (!code) return null;
  if (code in ERROR_REASONS) {
    return ERROR_REASONS[code as DocumentErrorCode];
  }
  return "Ingestion failed.";
}

export interface StatusPillProps {
  status: DocumentStatus;
  /** Typed (or unknown) error code; only rendered when status is `failed`. */
  errorCode?: DocumentErrorCode | string | null;
  className?: string;
}

export function StatusPill({ status, errorCode, className }: StatusPillProps) {
  const label = statusLabel(status);
  const animated = !isTerminalStatus(status);
  const reason = status === "failed" ? errorReason(errorCode) : null;

  // Accessible label: the visible text already names the state; for `failed`
  // we extend the announced text with the reason via the title + sr-only note.
  const ariaLabel = reason ? `${label}: ${reason}` : label;

  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
          STYLES[status],
          className,
        )}
        role="status"
        aria-label={ariaLabel}
        title={reason ?? label}
      >
        <span
          className={cn("h-1.5 w-1.5 rounded-full bg-current", animated && "animate-pulse")}
          aria-hidden="true"
        />
        {label}
      </span>
      {reason ? <span className="text-xs text-muted-foreground">{reason}</span> : null}
    </span>
  );
}
