"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";

import { MotionDiv } from "./motion";

export type ToastTone = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
  duration: number;
}

interface ToastApi {
  toast: (message: string, opts?: { tone?: ToastTone; duration?: number }) => void;
  success: (message: string, duration?: number) => void;
  error: (message: string, duration?: number) => void;
  info: (message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TONE_STYLES: Record<ToastTone, string> = {
  success: "border-success/40 bg-card text-foreground",
  error: "border-danger/40 bg-card text-foreground",
  info: "border-border bg-card text-foreground",
};

const TONE_DOT: Record<ToastTone, string> = {
  success: "bg-success",
  error: "bg-danger",
  info: "bg-accent",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counter = useRef(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, tone: ToastTone, duration: number) => {
      const id = ++counter.current;
      setToasts((prev) => [...prev, { id, message, tone, duration }]);
      if (duration > 0) {
        window.setTimeout(() => dismiss(id), duration);
      }
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      toast: (message, opts) => push(message, opts?.tone ?? "info", opts?.duration ?? 4000),
      success: (message, duration = 4000) => push(message, "success", duration),
      error: (message, duration = 6000) => push(message, "error", duration),
      info: (message, duration = 4000) => push(message, "info", duration),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      {mounted
        ? createPortal(
            <div
              className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end"
              aria-live="polite"
              aria-atomic="false"
            >
              {toasts.map((t) => (
                <MotionDiv
                  key={t.id}
                  variant="fade-up"
                  className={cn(
                    "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg",
                    TONE_STYLES[t.tone],
                  )}
                  role={t.tone === "error" ? "alert" : "status"}
                >
                  <span
                    className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", TONE_DOT[t.tone])}
                    aria-hidden="true"
                  />
                  <span className="flex-1 leading-snug">{t.message}</span>
                  <button
                    type="button"
                    onClick={() => dismiss(t.id)}
                    className="shrink-0 rounded text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    aria-label="Dismiss"
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <path
                        d="M4 4l8 8M12 4l-8 8"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                </MotionDiv>
              ))}
            </div>,
            document.body,
          )
        : null}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
