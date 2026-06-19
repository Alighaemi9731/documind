"use client";

import { forwardRef, useId } from "react";

import { cn } from "@/lib/cn";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<
  React.SelectHTMLAttributes<HTMLSelectElement>,
  "children"
> {
  label?: string;
  hideLabel?: boolean;
  error?: string | null;
  hint?: string | null;
  options: SelectOption[];
  /** Optional leading placeholder option. */
  placeholder?: string;
}

/**
 * Accessible native <select> styled to the design tokens. A native control is
 * intentional: it is keyboard-/touch-/screen-reader-correct and RTL-correct for
 * free, and keeps the bundle lean (no popover library).
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hideLabel, error, hint, options, placeholder, id, className, ...props },
  ref,
) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const errorId = `${selectId}-error`;
  const hintId = `${selectId}-hint`;
  const describedBy = error ? errorId : hint ? hintId : undefined;

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label
          htmlFor={selectId}
          className={cn("text-sm font-medium text-foreground", hideLabel && "sr-only")}
        >
          {label}
        </label>
      ) : null}
      <div className="relative">
        <select
          ref={ref}
          id={selectId}
          className={cn(
            "w-full appearance-none rounded-lg border border-border bg-background px-3 py-2 pe-9 text-sm text-foreground",
            "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/40",
            "disabled:cursor-not-allowed disabled:opacity-60",
            error && "border-danger focus:border-danger focus:ring-danger/30",
            className,
          )}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...props}
        >
          {placeholder ? (
            <option value="" disabled>
              {placeholder}
            </option>
          ) : null}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </select>
        <span
          className="pointer-events-none absolute inset-y-0 end-3 flex items-center text-muted-foreground"
          aria-hidden="true"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d="M3 4.5 6 7.5 9 4.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </div>
      {error ? (
        <p id={errorId} className="text-xs text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
});
