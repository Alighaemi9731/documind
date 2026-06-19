import { CitationChip, citationLocation } from "@/components/chat/CitationChip";
import { cn } from "@/lib/cn";
import type { Citation } from "@/lib/types";

/**
 * The sources list for an assistant answer (ARCHITECTURE.md §8/§11). Each entry
 * shows the citation chip plus the retrieved snippet so the user can see the
 * supporting evidence. Snippets are document-derived text and are rendered as
 * plain strings (React escapes them) — never as markup.
 *
 * The server has already validated every citation against the exact retrieved
 * chunk-id set (ADR-0008), so the panel renders whatever it receives.
 */
export interface SourcesPanelProps {
  citations: Citation[];
  className?: string;
}

export function SourcesPanel({ citations, className }: SourcesPanelProps) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <section
      className={cn("flex flex-col gap-2", className)}
      aria-label={`Sources (${citations.length})`}
    >
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Sources
      </h3>
      <ul className="flex flex-col gap-2">
        {citations.map((citation, idx) => {
          const location = citationLocation(citation);
          return (
            <li
              key={citation.chunk_id || `${citation.document_id}-${citation.chunk_index}`}
              className="rounded-xl border border-border bg-card p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <CitationChip citation={citation} index={idx + 1} />
                {location ? (
                  <span className="shrink-0 text-[0.7rem] text-muted-foreground">{location}</span>
                ) : null}
              </div>
              {citation.snippet ? (
                <p
                  className="mt-2 line-clamp-3 text-xs leading-relaxed text-muted-foreground"
                  dir="auto"
                >
                  {citation.snippet}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
