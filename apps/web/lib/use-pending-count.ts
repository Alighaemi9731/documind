"use client";

/**
 * Admin-only: number of pending registrations, used for the nav badge. Only
 * fetches when the viewer is an admin AND registration is in approval mode (the
 * queue is meaningless otherwise). Polls lazily on a slow interval and pauses on
 * a hidden tab to stay cheap.
 */

import { useCallback, useEffect, useState } from "react";

import { pendingRegistrations } from "./admin";
import { getAppConfig } from "./config";

const POLL_MS = 60_000;

export function usePendingCount(isAdmin: boolean): number {
  const [count, setCount] = useState(0);

  const load = useCallback(async () => {
    try {
      const config = await getAppConfig();
      if (config.registration_mode !== "approval") {
        setCount(0);
        return;
      }
      const pending = await pendingRegistrations();
      setCount(pending.length);
    } catch {
      // Non-fatal: the badge just stays at its last value.
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      setCount(0);
      return;
    }
    void load();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [isAdmin, load]);

  return count;
}
