"use client";

import { useCallback, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";

import { MotionDiv } from "./motion";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  /** Footer actions (buttons). */
  footer?: React.ReactNode;
  /** Constrain width. */
  size?: "sm" | "md" | "lg";
  /** When false, clicking the backdrop does NOT close (e.g. destructive confirm). */
  dismissOnBackdrop?: boolean;
}

const SIZES = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
} as const;

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Accessible dialog: focus-trap, Esc-to-close, restores focus to the opener,
 * `role="dialog"` + `aria-modal`, labelled by its title. Rendered in a portal so
 * it escapes overflow/stacking contexts. Animated via the lazy MotionDiv (Framer
 * is never in the initial chunk).
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  dismissOnBackdrop = true,
}: ModalProps) {
  const titleId = useId();
  const descId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  // Esc-to-close + focus trap, on a DOCUMENT-level capture listener. The panel is
  // rendered in a portal (document.body), so a React onKeyDown on the portal
  // subtree is not reliably reached by native key events that originate outside
  // the React root container (jsdom/userEvent). A capture-phase document listener
  // sees every Tab/Escape and can preventDefault BEFORE the browser (or
  // userEvent) performs its own focus move.
  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      // Visible, focusable nodes. We avoid an `offsetParent` visibility check so
      // the trap also works in layout-less environments (jsdom tests); the
      // selector already excludes disabled controls, and `hidden` is filtered.
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (n) => !n.hasAttribute("hidden") && n.getAttribute("aria-hidden") !== "true",
      );
      if (nodes.length === 0) {
        e.preventDefault();
        return;
      }
      // Manage Tab explicitly so focus always CYCLES within the panel
      // (deterministic across browsers and jsdom/userEvent — not only at the
      // first/last boundary).
      e.preventDefault();
      const active = document.activeElement as HTMLElement | null;
      const idx = active ? nodes.indexOf(active) : -1;
      const nextIndex = e.shiftKey
        ? idx <= 0
          ? nodes.length - 1
          : idx - 1
        : idx === -1 || idx === nodes.length - 1
          ? 0
          : idx + 1;
      nodes[nextIndex].focus();
    },
    [onClose],
  );

  // Lock scroll, bind the key trap, move focus into the panel; restore on close.
  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown, true);
    // Defer focus until the portal content is painted.
    const t = window.setTimeout(() => {
      const panel = panelRef.current;
      if (!panel) return;
      const focusable = panel.querySelector<HTMLElement>(FOCUSABLE);
      (focusable ?? panel).focus();
    }, 0);
    return () => {
      window.clearTimeout(t);
      document.removeEventListener("keydown", onKeyDown, true);
      document.body.style.overflow = overflow;
      previouslyFocused.current?.focus?.();
    };
  }, [open, onKeyDown]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        aria-hidden="true"
        onClick={dismissOnBackdrop ? onClose : undefined}
      />
      <MotionDiv
        variant="scale"
        className={cn(
          "relative z-10 w-full rounded-2xl border border-border bg-card text-card-foreground shadow-xl",
          SIZES[size],
        )}
        role="dialog"
        aria-modal={true}
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
      >
        <div ref={panelRef} tabIndex={-1} className="flex flex-col outline-none">
          <div className="flex flex-col gap-1 p-6 pb-2">
            <h2 id={titleId} className="text-lg font-semibold tracking-tight">
              {title}
            </h2>
            {description ? (
              <p id={descId} className="text-sm text-muted-foreground">
                {description}
              </p>
            ) : null}
          </div>
          <div className="px-6 py-2 text-sm">{children}</div>
          {footer ? (
            <div className="flex items-center justify-end gap-3 p-6 pt-4">{footer}</div>
          ) : null}
        </div>
      </MotionDiv>
    </div>,
    document.body,
  );
}
