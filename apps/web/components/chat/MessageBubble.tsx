import { CitationChip } from "@/components/chat/CitationChip";
import { cn } from "@/lib/cn";
import { SafeMarkdown } from "@/lib/safe-markdown";
import type { Citation } from "@/lib/types";

/**
 * A single chat message (ARCHITECTURE.md §11).
 *
 * User turns render their text plainly. Assistant turns render the streamed
 * answer via SAFE markdown (HTML disabled, no dangerouslySetInnerHTML) and, when
 * grounded, the inline citation chips beneath the answer.
 *
 * Grounding (ADR-0008): the `grounded` flag is the AUTHORITATIVE server signal
 * carried by the `done` event — it is NEVER derived from the answer text. When
 * `grounded === false` the bubble switches to a visually distinct "Not in your
 * documents" guarded state showing the refusal text the server returned.
 */
export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  /** Accumulated text (assistant: the streamed answer or the refusal text). */
  text: string;
  citations: Citation[];
  /**
   * Authoritative grounding from the `done` event. `null` while the assistant
   * turn is still streaming (before `done` arrives) or for user turns.
   */
  grounded: boolean | null;
  /** True while this assistant turn is actively receiving tokens. */
  streaming?: boolean;
  /** A request-level error (e.g. quota/isolation) instead of an answer. */
  error?: string | null;
  /**
   * Durable server message id from the `done` event (ADR-0017). Stable handle
   * for citations/feedback once the turn has settled; absent while streaming.
   */
  messageId?: string;
}

export interface MessageBubbleProps {
  message: ChatMessage;
  onSelectCitation?: (citation: Citation) => void;
}

export function MessageBubble({ message, onSelectCitation }: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end" data-role="user">
        <div
          className="max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-sm text-accent-foreground"
          dir="auto"
        >
          {message.text}
        </div>
      </div>
    );
  }

  // Assistant turn.
  const isGuarded = message.grounded === false && !message.error;

  return (
    <div className="flex justify-start" data-role="assistant">
      <div className="flex max-w-[85%] flex-col gap-2">
        {message.error ? (
          <div
            role="alert"
            className="rounded-2xl rounded-bl-sm border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-600 dark:text-red-400"
          >
            {message.error}
          </div>
        ) : isGuarded ? (
          <GuardedAnswer text={message.text} />
        ) : (
          <div
            className="rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-2.5 text-card-foreground"
            data-grounded={message.grounded === true ? "true" : undefined}
          >
            <SafeMarkdown content={message.text} />
            {message.streaming ? (
              <span
                className="ms-0.5 inline-block h-4 w-1.5 animate-pulse bg-current align-text-bottom"
                aria-hidden="true"
              />
            ) : null}
          </div>
        )}

        {/* Inline citation chips only on a grounded, settled answer. */}
        {!isGuarded && !message.error && message.citations.length > 0 ? (
          <div className="flex flex-wrap gap-1.5" aria-label="Citations">
            {message.citations.map((citation, idx) => (
              <CitationChip
                key={citation.chunk_id || `${citation.document_id}-${citation.chunk_index}`}
                citation={citation}
                index={idx + 1}
                onSelect={onSelectCitation}
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/**
 * The explicit, visually distinct "Not in your documents" state shown when the
 * retrieval-score grounding gate refused (grounded=false, ADR-0008). It uses a
 * warning-toned surface that is clearly different from a normal answer so users
 * are never misled into thinking a refusal is a grounded answer.
 */
function GuardedAnswer({ text }: { text: string }) {
  const fallback = "I couldn't find an answer to that in your documents.";
  return (
    <div
      className={cn(
        "rounded-2xl rounded-bl-sm border border-amber-500/40 bg-amber-500/10 px-4 py-3",
        "text-sm text-amber-700 dark:text-amber-300",
      )}
      data-grounded="false"
      role="note"
    >
      <p className="mb-1 flex items-center gap-1.5 font-medium">
        <span aria-hidden="true">⚠</span>
        Not in your documents
      </p>
      <p className="text-amber-700/90 dark:text-amber-300/90" dir="auto">
        {text.trim() || fallback}
      </p>
    </div>
  );
}
