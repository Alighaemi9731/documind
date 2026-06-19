"use client";

import { useCallback, useEffect, useState } from "react";

import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import {
  type AdminUser,
  approveRegistration,
  pendingRegistrations,
  rejectRegistration,
} from "@/lib/admin";
import { ApiError } from "@/lib/api";
import { direction } from "@/lib/direction";

/**
 * Pending-approval queue (only mounted when registration_mode === "approval").
 * Approve → account becomes active; reject → account is deleted.
 */
export function RegistrationsSection({ onChange }: { onChange?: () => void }) {
  const toast = useToast();
  const [pending, setPending] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setError(null);
    try {
      setPending(await pendingRegistrations());
    } catch (err) {
      setPending([]);
      setError(err instanceof ApiError ? err.message : "Could not load the queue.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(user: AdminUser, kind: "approve" | "reject") {
    setBusy((prev) => ({ ...prev, [user.id]: true }));
    try {
      if (kind === "approve") {
        await approveRegistration(user.id);
        toast.success(`Approved ${user.email}.`);
      } else {
        await rejectRegistration(user.id);
        toast.success(`Rejected ${user.email}.`);
      }
      setPending((prev) => (prev ? prev.filter((u) => u.id !== user.id) : prev));
      onChange?.();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed.");
    } finally {
      setBusy((prev) => {
        const next = { ...prev };
        delete next[user.id];
        return next;
      });
    }
  }

  if (pending === null) {
    return <Skeleton className="h-32 w-full rounded-2xl" />;
  }

  return (
    <div className="flex flex-col gap-3">
      <FormError message={error} />
      {pending.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center text-sm text-muted-foreground">
          No pending registrations.
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {pending.map((u) => (
            <li key={u.id}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
                <span className="font-medium" dir={direction(u.email)}>
                  {u.email}
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void act(u, "reject")}
                    loading={busy[u.id]}
                  >
                    Reject
                  </Button>
                  <Button size="sm" onClick={() => void act(u, "approve")} loading={busy[u.id]}>
                    Approve
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
