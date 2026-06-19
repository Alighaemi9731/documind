"use client";

import { useEffect, useState } from "react";

import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { type AdminUser, getQuota, setQuota } from "@/lib/admin";
import { ApiError } from "@/lib/api";

/**
 * Per-user shared-key quota editor (ARCHITECTURE.md §10). Empty number fields
 * mean "use the install default" (sent as null). `hard_disabled` blocks all
 * shared-key usage for the user.
 */
export function UserQuotaModal({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [monthly, setMonthly] = useState("");
  const [perDay, setPerDay] = useState("");
  const [hardDisabled, setHardDisabled] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const q = await getQuota(user.id);
        if (!active) return;
        setMonthly(q.monthly_token_limit != null ? String(q.monthly_token_limit) : "");
        setPerDay(q.requests_per_day != null ? String(q.requests_per_day) : "");
        setHardDisabled(q.hard_disabled);
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.message : "Could not load quota.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user.id]);

  function parseNumber(value: string): number | null {
    const trimmed = value.trim();
    if (trimmed === "") return null;
    const n = Number(trimmed);
    return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
  }

  async function onSave() {
    setSaving(true);
    setError(null);
    try {
      await setQuota(user.id, {
        monthly_token_limit: parseNumber(monthly),
        requests_per_day: parseNumber(perDay),
        hard_disabled: hardDisabled,
      });
      toast.success("Quota updated.");
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save quota.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      onClose={() => (saving ? undefined : onClose())}
      dismissOnBackdrop={!saving}
      title="Edit quota"
      description={user.email}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void onSave()} loading={saving} disabled={loading}>
            Save
          </Button>
        </>
      }
    >
      {loading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <FormError message={error} />
          <Input
            label="Monthly token limit"
            type="number"
            inputMode="numeric"
            min={0}
            value={monthly}
            onChange={(e) => setMonthly(e.target.value)}
            hint="Blank = install default. Shared key only (BYOK is unmetered)."
          />
          <Input
            label="Requests per day"
            type="number"
            inputMode="numeric"
            min={0}
            value={perDay}
            onChange={(e) => setPerDay(e.target.value)}
            hint="Blank = install default."
          />
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={hardDisabled}
              onChange={(e) => setHardDisabled(e.target.checked)}
              className="h-4 w-4 rounded border-border text-accent focus-visible:ring-2 focus-visible:ring-ring"
            />
            Hard-disable shared-key usage for this user
          </label>
        </div>
      )}
    </Modal>
  );
}
