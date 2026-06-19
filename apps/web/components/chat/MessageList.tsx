"use client";

import { useEffect, useRef } from "react";

import { MessageBubble, type ChatMessage } from "@/components/chat/MessageBubble";
import { SourcesPanel } from "@/components/chat/SourcesPanel";
import type { Citation } from "@/lib/types";

/**
 * Scrollable conversation transcript for the session (ARCHITECTURE.md §11,
 * ADR-0017: history is persisted; this renders the in-session turns). It
 * auto-scrolls to the newest message as tokens stream in and exposes an
 * `aria-live` region so assistant output is announced to screen readers.
 *
 * Each assistant turn renders its own inline citation chips (in MessageBubble);
 * the SourcesPanel for the LATEST grounded answer is shown beneath the list so
 * the user always sees the supporting evidence for the current answer.
 */
export interface MessageListProps {
  messages: ChatMessage[];
  onSelectCitation?: (citation: Citation) => void;
}

export function MessageList({ messages, onSelectCitation }: MessageListProps) {
  const endRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to the bottom as new messages/tokens arrive.
  const lastText = messages[messages.length - 1]?.text;
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, lastText]);

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const showSources =
    lastAssistant != null &&
    lastAssistant.grounded === true &&
    !lastAssistant.error &&
    lastAssistant.citations.length > 0;

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-12 text-center">
        <p className="text-sm font-medium text-card-foreground">Ask your documents a question</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          Answers are drawn strictly from this project&apos;s documents, with citations. If the
          answer isn&apos;t there, you&apos;ll be told plainly.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-1 py-2">
      <div className="flex flex-col gap-4" role="log" aria-live="polite" aria-label="Conversation">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} onSelectCitation={onSelectCitation} />
        ))}
      </div>

      {showSources ? <SourcesPanel citations={lastAssistant.citations} className="mt-1" /> : null}

      <div ref={endRef} />
    </div>
  );
}
