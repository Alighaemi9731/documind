"use client";

import { forwardRef, useId } from "react";

import { cn } from "@/lib/cn";

/**
 * Masked secret field for BYOK keys (ARCHITECTURE.md §9, §14).
 *
 * SECRETS NEVER LEAVE THE SERVER and are never displayed: when a key is already
 * saved we render a non-editable "connected" affordance showing ONLY its
 * fingerprint (last-4 + sha256 prefix) — never the value, which the API does not
 * return. To paste a new/replacement key the caller flips `editing` on, which
 * shows a write-only password input. The typed value lives only in the caller's
 * transient state and is cleared after a successful save.
 */
export interface MaskedSecretInputProps {
  label: string;
  /** True when a key is already stored server-side. */
  connected: boolean;
  /** Non-secret fingerprint of the stored key (shown when connected). */
  fingerprint?: string | null;
  /** When true, render the write-only paste input instead of the masked state. */
  editing: boolean;
  /** Bound value of the paste input (caller-owned, never persisted). */
  value: string;
  onChange: (value: string) => void;
  /** Field-level error (e.g. validation failure). */
  error?: string | null;
  /** Optional hint (e.g. expected key format). */
  hint?: string | null;
  placeholder?: string;
  disabled?: boolean;
}

export const MaskedSecretInput = forwardRef<HTMLInputElement, MaskedSecretInputProps>(
  function MaskedSecretInput(
    { label, connected, fingerprint, editing, value, onChange, error, hint, placeholder, disabled },
    ref,
  ) {
    const inputId = useId();
    const errorId = `${inputId}-error`;
    const hintId = `${inputId}-hint`;
    const describedBy = error ? errorId : hint ? hintId : undefined;

    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-sm font-medium text-foreground">
          {label}
        </label>

        {!editing && connected ? (
          // Masked "connected" state: fingerprint only, never the value.
          <div
            id={inputId}
            className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm text-foreground"
            data-testid="masked-secret-connected"
          >
            <span aria-hidden="true" className="font-mono tracking-widest text-muted-foreground">
              ••••••••
            </span>
            {fingerprint ? (
              <span className="font-mono text-xs text-muted-foreground">
                <span className="sr-only">Key fingerprint </span>
                {fingerprint}
              </span>
            ) : null}
          </div>
        ) : (
          // Write-only paste input. type=password so the value is masked while
          // typing; autoComplete off so no browser persists it.
          <input
            ref={ref}
            id={inputId}
            type="password"
            inputMode="text"
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            data-1p-ignore
            data-lpignore="true"
            value={value}
            disabled={disabled}
            placeholder={placeholder ?? "Paste your API key"}
            onChange={(e) => onChange(e.target.value)}
            className={cn(
              "w-full rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm text-foreground",
              "placeholder:font-sans placeholder:text-muted-foreground",
              "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/40",
              error && "border-red-500 focus:border-red-500 focus:ring-red-500/40",
            )}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
          />
        )}

        {error ? (
          <p id={errorId} className="text-xs text-red-500">
            {error}
          </p>
        ) : hint ? (
          <p id={hintId} className="text-xs text-muted-foreground">
            {hint}
          </p>
        ) : null}
      </div>
    );
  },
);
