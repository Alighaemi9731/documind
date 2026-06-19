"use client";

/**
 * Adaptive document-status polling hook (ARCHITECTURE.md §11, ADR-0012).
 *
 * Polls GET /api/projects/{id}/documents and re-schedules itself on a ~2s base
 * interval **while any document is non-terminal**. When every document reaches a
 * terminal state (ready/failed) it stops polling entirely (the next change comes
 * from an upload/reprocess that calls `refresh`). It also:
 *   - applies exponential backoff (2s → up to 30s) on consecutive request
 *     failures, so a flaky/overloaded API is not hammered;
 *   - pauses while the tab is hidden (`visibilitychange`) and resumes (with an
 *     immediate poll) when it becomes visible again — saving the API and battery;
 *   - never holds two timers at once and cleans up on unmount.
 *
 * Deliberately TanStack-Query-free: this is a self-contained setTimeout loop so
 * the project view has one obvious source of truth for polling.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "./api";
import { listDocuments } from "./documents";
import type { DocumentItem, DocumentStatus } from "./types";

const TERMINAL: ReadonlySet<DocumentStatus> = new Set(["ready", "failed"]);
const BASE_INTERVAL_MS = 2000;
const MAX_BACKOFF_MS = 30000;

function anyNonTerminal(docs: DocumentItem[]): boolean {
  return docs.some((d) => !TERMINAL.has(d.status));
}

export interface UseDocumentStatusResult {
  documents: DocumentItem[] | null;
  /** True only on the very first load (so the UI can show a skeleton). */
  isLoading: boolean;
  /** Set when the most recent poll failed; cleared on the next success. */
  error: string | null;
  /** True while at least one document is still being ingested. */
  isPolling: boolean;
  /** Force an immediate refresh (after upload / reprocess / delete). */
  refresh: () => Promise<void>;
}

export function useDocumentStatus(projectId: string): UseDocumentStatusResult {
  const [documents, setDocuments] = useState<DocumentItem[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  // Mutable scheduling state kept in refs so the effect identity is stable.
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const failuresRef = useRef(0);
  const mountedRef = useRef(true);
  const pollRef = useRef<() => Promise<void>>(async () => {});

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const schedule = useCallback(
    (delayMs: number) => {
      clearTimer();
      // Never schedule while the tab is hidden; visibilitychange resumes us.
      if (typeof document !== "undefined" && document.hidden) {
        return;
      }
      timerRef.current = setTimeout(() => {
        void pollRef.current();
      }, delayMs);
    },
    [clearTimer],
  );

  const poll = useCallback(async () => {
    try {
      const docs = await listDocuments(projectId);
      if (!mountedRef.current) return;
      failuresRef.current = 0;
      setDocuments(docs);
      setError(null);
      setIsLoading(false);

      if (anyNonTerminal(docs)) {
        setIsPolling(true);
        schedule(BASE_INTERVAL_MS);
      } else {
        setIsPolling(false);
        clearTimer();
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setIsLoading(false);
      // A 401 means the access token expired; apiFetch already attempted a
      // silent refresh, so surface a generic message and back off.
      setError(err instanceof ApiError ? err.message : "Could not refresh document status.");
      failuresRef.current += 1;
      const backoff = Math.min(BASE_INTERVAL_MS * 2 ** failuresRef.current, MAX_BACKOFF_MS);
      // Keep retrying only if we believe ingestion is ongoing (or unknown).
      if (documents === null || anyNonTerminal(documents)) {
        setIsPolling(true);
        schedule(backoff);
      } else {
        setIsPolling(false);
      }
    }
  }, [projectId, schedule, clearTimer, documents]);

  // Keep the latest poll callback reachable from timers without re-arming them.
  pollRef.current = poll;

  const refresh = useCallback(async () => {
    failuresRef.current = 0;
    await pollRef.current();
  }, []);

  // Initial load + cleanup. Re-runs when the project changes.
  useEffect(() => {
    mountedRef.current = true;
    failuresRef.current = 0;
    setIsLoading(true);
    setDocuments(null);
    void pollRef.current();
    return () => {
      mountedRef.current = false;
      clearTimer();
    };
  }, [projectId, clearTimer]);

  // Pause on hidden tab; on becoming visible, poll immediately if anything is
  // still non-terminal (or if we have never loaded yet).
  useEffect(() => {
    function onVisibility() {
      if (typeof document === "undefined") return;
      if (document.hidden) {
        clearTimer();
      } else if (documents === null || anyNonTerminal(documents)) {
        void pollRef.current();
      }
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [documents, clearTimer]);

  return { documents, isLoading, error, isPolling, refresh };
}
