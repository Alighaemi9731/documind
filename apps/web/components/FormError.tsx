import { cn } from "@/lib/cn";

export interface FormErrorProps {
  /** Form-level (non-field) error message; nothing renders when empty. */
  message?: string | null;
  className?: string;
}

/**
 * Form-level error banner. Field-specific errors are rendered inline by
 * {@link Input} via its `error` prop; this surfaces form-wide failures
 * (e.g. invalid credentials, server errors) using role="alert".
 */
export function FormError({ message, className }: FormErrorProps) {
  if (!message) {
    return null;
  }
  return (
    <div
      role="alert"
      className={cn(
        "rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400",
        className,
      )}
    >
      {message}
    </div>
  );
}
