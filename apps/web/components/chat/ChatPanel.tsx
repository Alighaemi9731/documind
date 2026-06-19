"use client";

import { Composer } from "@/components/chat/Composer";
import { MessageList } from "@/components/chat/MessageList";
import { useChat } from "@/lib/use-chat";

/**
 * The chat Q&A surface for a project (ARCHITECTURE.md §8/§11). Wires the
 * streaming client (lib/chat.ts via useChat) to the transcript + composer:
 * tokens stream into the latest assistant bubble, inline citation chips render
 * beneath a grounded answer, the SourcesPanel shows the supporting snippets, and
 * a guarded "Not in your documents" state appears when grounded=false.
 *
 * Single-turn in v1 (ADR-0017): each question retrieves on its own text; the
 * session transcript is shown but earlier turns do not rewrite later retrieval.
 */
export interface ChatPanelProps {
  projectId: string;
}

export function ChatPanel({ projectId }: ChatPanelProps) {
  const { messages, streaming, ask, stop } = useChat(projectId);

  return (
    <div className="flex h-[32rem] flex-col overflow-hidden rounded-2xl border border-border bg-background">
      <MessageList messages={messages} />
      <Composer onSend={ask} onStop={stop} streaming={streaming} />
    </div>
  );
}
