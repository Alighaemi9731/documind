"use client";

import { useId, useRef, useState } from "react";

import { Button } from "@/components/Button";
import { cn } from "@/lib/cn";

/**
 * Chat input (ARCHITECTURE.md §11). A growing textarea plus a send button. While
 * a turn is streaming the input and Send are disabled and a Stop button is
 * offered to abort the in-flight request.
 *
 * Submit on Enter (Shift+Enter inserts a newline). The textarea auto-detects
 * direction (`dir="auto"`) for mixed Persian/English input.
 */
export interface ComposerProps {
  onSend: (question: string) => void;
  onStop?: () => void;
  /** True while an answer is streaming — disables input/Send, shows Stop. */
  streaming?: boolean;
  disabled?: boolean;
}

const MAX_ROWS = 6;

export function Composer({ onSend, onStop, streaming = false, disabled = false }: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const inputId = useId();

  const canSend = value.trim().length > 0 && !streaming && !disabled;

  function autoGrow(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    const lineHeight = 24;
    const max = lineHeight * MAX_ROWS;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
  }

  function submit() {
    const question = value.trim();
    if (!question || streaming || disabled) return;
    onSend(question);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form
      className="flex items-end gap-2 border-t border-border bg-background p-3"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor={inputId} className="sr-only">
        Ask a question about your documents
      </label>
      <textarea
        ref={textareaRef}
        id={inputId}
        value={value}
        rows={1}
        dir="auto"
        disabled={streaming || disabled}
        placeholder="Ask a question about your documents…"
        onChange={(event) => {
          setValue(event.target.value);
          autoGrow(event.target);
        }}
        onKeyDown={onKeyDown}
        className={cn(
          "min-h-[2.5rem] flex-1 resize-none rounded-xl border border-border bg-card px-3 py-2 text-sm",
          "text-card-foreground placeholder:text-muted-foreground",
          "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/40",
          "disabled:cursor-not-allowed disabled:opacity-60",
        )}
      />
      {streaming ? (
        <Button type="button" variant="secondary" onClick={onStop}>
          Stop
        </Button>
      ) : (
        <Button type="submit" disabled={!canSend}>
          Send
        </Button>
      )}
    </form>
  );
}
