"use client";

import { forwardRef, useId } from "react";

import { cn } from "@/lib/cn";
import { direction } from "@/lib/direction";

/** Shared field-shell props for label + error/hint wiring. */
interface FieldShellProps {
  label?: string;
  /** Field-level error; sets aria-invalid and links via aria-describedby. */
  error?: string | null;
  /** Helper text shown below the field when there is no error. */
  hint?: string | null;
  /** Visually hide the label (still announced to screen readers). */
  hideLabel?: boolean;
}

const controlBase =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground " +
  "placeholder:text-muted-foreground transition-[border-color,box-shadow] " +
  "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/40 " +
  "disabled:cursor-not-allowed disabled:opacity-60";

const controlError = "border-danger focus:border-danger focus:ring-danger/30";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement>, FieldShellProps {
  /** When true, auto-detect text direction from the value (mixed fa/en). */
  autoDir?: boolean;
}

/**
 * Labelled, accessible text input. `autoDir` flips the field `dir` to match the
 * value's first strong character so a Persian name aligns RTL while an English
 * one stays LTR (ARCHITECTURE.md §11). Uses CSS logical properties everywhere.
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, hideLabel, autoDir, id, className, dir, value, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const describedBy = error ? errorId : hint ? hintId : undefined;
  const resolvedDir =
    dir ?? (autoDir ? direction(typeof value === "string" ? value : "") : undefined);

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label
          htmlFor={inputId}
          className={cn("text-sm font-medium text-foreground", hideLabel && "sr-only")}
        >
          {label}
        </label>
      ) : null}
      <input
        ref={ref}
        id={inputId}
        dir={resolvedDir}
        value={value}
        className={cn(controlBase, error && controlError, className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
      />
      <FieldMessage error={error} hint={hint} errorId={errorId} hintId={hintId} />
    </div>
  );
});

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement>, FieldShellProps {
  autoDir?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, hint, hideLabel, autoDir, id, className, dir, value, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const describedBy = error ? errorId : hint ? hintId : undefined;
  const resolvedDir =
    dir ?? (autoDir ? direction(typeof value === "string" ? value : "") : undefined);

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label
          htmlFor={inputId}
          className={cn("text-sm font-medium text-foreground", hideLabel && "sr-only")}
        >
          {label}
        </label>
      ) : null}
      <textarea
        ref={ref}
        id={inputId}
        dir={resolvedDir}
        value={value}
        className={cn(controlBase, "min-h-[5rem] resize-y", error && controlError, className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
      />
      <FieldMessage error={error} hint={hint} errorId={errorId} hintId={hintId} />
    </div>
  );
});

function FieldMessage({
  error,
  hint,
  errorId,
  hintId,
}: {
  error?: string | null;
  hint?: string | null;
  errorId: string;
  hintId: string;
}) {
  if (error) {
    return (
      <p id={errorId} className="text-xs text-danger">
        {error}
      </p>
    );
  }
  if (hint) {
    return (
      <p id={hintId} className="text-xs text-muted-foreground">
        {hint}
      </p>
    );
  }
  return null;
}
