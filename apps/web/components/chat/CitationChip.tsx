import { cn } from "@/lib/cn";
import type { Citation } from "@/lib/types";

/**
 * A compact, accessible citation chip: filename plus an optional page number
 * (ARCHITECTURE.md §6/§11). The filename is document-derived text and is
 * rendered as a plain string (React escapes it) — never as markup.
 *
 * Rendered inline beneath an assistant answer and inside the SourcesPanel. When
 * `index` is provided it shows a small ordinal (the bracketed number the answer
 * may reference). Optionally clickable to focus the matching source.
 */
export interface CitationChipProps {
  citation: Citation;
  /** 1-based ordinal shown as a small badge (e.g. the answer's [1] marker). */
  index?: number;
  onSelect?: (citation: Citation) => void;
  className?: string;
}

/** Human label for a citation's location: "p.3" / "§Intro" / "#12". */
export function citationLocation(citation: Citation): string | null {
  if (citation.page != null) return `p.${citation.page}`;
  if (citation.section_path) return `§${citation.section_path}`;
  return `#${citation.chunk_index}`;
}

export function CitationChip({ citation, index, onSelect, className }: CitationChipProps) {
  const location = citationLocation(citation);
  const label = `Source${index != null ? ` ${index}` : ""}: ${citation.filename}${
    location ? `, ${location}` : ""
  }`;

  const inner = (
    <>
      {index != null ? (
        <span
          className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-accent/15 px-1 text-[0.65rem] font-semibold text-accent"
          aria-hidden="true"
        >
          {index}
        </span>
      ) : null}
      <span className="max-w-[16ch] truncate" title={citation.filename}>
        {citation.filename}
      </span>
      {location ? <span className="text-muted-foreground">{location}</span> : null}
    </>
  );

  const baseClass = cn(
    "inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs",
    "text-card-foreground",
    className,
  );

  if (onSelect) {
    return (
      <button
        type="button"
        onClick={() => onSelect(citation)}
        className={cn(
          baseClass,
          "transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-background",
        )}
        aria-label={label}
      >
        {inner}
      </button>
    );
  }

  return (
    <span className={baseClass} aria-label={label} dir="auto">
      {inner}
    </span>
  );
}
