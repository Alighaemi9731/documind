"use client";

/**
 * Conversation state + streaming orchestration for the chat surface
 * (ARCHITECTURE.md §6/§8, ADR-0008/0017).
 *
 * Owns the in-session message list and drives lib/chat.ts:
 *   - appends the user turn and an empty assistant turn;
 *   - consumes the async-iterator of stream events, appending `token` deltas,
 *     replacing the assistant `citations`, and settling `grounded` + the durable
 *     `message_id` from the terminal `done` event;
 *   - on a request error (e.g. 429 quota / 403 isolation) attaches an error to
 *     the assistant turn instead of an answer;
 *   - supports aborting the in-flight stream (Composer "Stop" / unmount).
 *
 * Grounding is taken ONLY from the `done` event (the server strips the sentinel
 * and is the sole trust anchor) — never inferred from token text.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "./api";
import { streamQuery } from "./chat";
import type { Citation } from "./types";
import type { ChatMessage } from "@/components/chat/MessageBubble";

let messageCounter = 0;
function localId(prefix: string): string {
  messageCounter += 1;
  return `${prefix}-${Date.now()}-${messageCounter}`;
}

export interface UseChatResult {
  messages: ChatMessage[];
  /** True while an answer is streaming. */
  streaming: boolean;
  /** Submit a question; no-op while already streaming. */
  ask: (question: string) => void;
  /** Abort the in-flight stream (keeps whatever tokens already arrived). */
  stop: () => void;
}

export function useChat(projectId: string): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Abort any in-flight stream on unmount / project change.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, [projectId]);

  const patchAssistant = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  }, []);

  const appendToken = useCallback((id: string, text: string) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, text: m.text + text } : m)));
  }, []);

  const ask = useCallback(
    (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || streaming) return;

      const userMessage: ChatMessage = {
        id: localId("user"),
        role: "user",
        text: trimmed,
        citations: [],
        grounded: null,
      };
      const assistantId = localId("assistant");
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        text: "",
        citations: [],
        grounded: null,
        streaming: true,
      };
      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      void (async () => {
        let citations: Citation[] = [];
        try {
          for await (const event of streamQuery(projectId, trimmed, {
            signal: controller.signal,
          })) {
            if (event.type === "token") {
              appendToken(assistantId, event.text);
            } else if (event.type === "citations") {
              citations = event.citations;
              patchAssistant(assistantId, { citations });
            } else if (event.type === "done") {
              patchAssistant(assistantId, {
                grounded: event.grounded,
                streaming: false,
                citations,
                messageId: event.messageId,
              });
            } else if (event.type === "error") {
              // Terminal error frame (provider/resolver failure mid-stream).
              patchAssistant(assistantId, { streaming: false, error: event.message });
            }
          }
          // If the stream ended without a `done` event, settle fail-closed.
          patchAssistant(assistantId, { streaming: false });
        } catch (err) {
          if (controller.signal.aborted) {
            patchAssistant(assistantId, { streaming: false });
            return;
          }
          const message =
            err instanceof ApiError
              ? err.message
              : "Something went wrong while answering. Please try again.";
          patchAssistant(assistantId, { streaming: false, error: message });
        } finally {
          if (abortRef.current === controller) {
            abortRef.current = null;
          }
          setStreaming(false);
        }
      })();
    },
    [projectId, streaming, appendToken, patchAssistant],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { messages, streaming, ask, stop };
}
