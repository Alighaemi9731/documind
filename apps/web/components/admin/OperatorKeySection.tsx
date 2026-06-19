"use client";

import { useCallback, useEffect, useState } from "react";

import { FormError } from "@/components/FormError";
import { MaskedSecretInput } from "@/components/settings/MaskedSecretInput";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { getOperatorKey, type OperatorKey, rotateOperatorKey } from "@/lib/admin";
import { ApiError } from "@/lib/api";

/**
 * Operator-default (shared Gemini) key oversight: shows the FINGERPRINT only
 * (never the secret, §14) and offers a confirm-gated rotate. The new key is
 * write-only — it is sent once and never echoed back.
 */
export function OperatorKeySection() {
  const toast = useToast();
  const [key, setKey] = useState<OperatorKey | null | "missing">(null);
  const [error, setError] = useState<string | null>(null);

  const [showRotate, setShowRotate] = useState(false);
  const [value, setValue] = useState("");
  const [rotateError, setRotateError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setKey(await getOperatorKey());
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setKey("missing");
      } else {
        setError(err instanceof ApiError ? err.message : "Could not load the operator key.");
      }
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRotate() {
    const trimmed = value.trim();
    if (!trimmed) {
      setRotateError("Paste the new key.");
      return;
    }
    setSaving(true);
    setRotateError(null);
    try {
      const updated = await rotateOperatorKey(trimmed);
      setValue("");
      setKey(updated);
      setShowRotate(false);
      toast.success("Operator key rotated.");
    } catch (err) {
      setRotateError(err instanceof ApiError ? err.message : "Could not rotate the key.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex flex-col gap-1">
        <h3 className="text-base font-semibold">Operator default key</h3>
        <p className="text-sm text-muted-foreground">
          The shared Gemini key all users fall back to. Only the fingerprint is ever shown.
        </p>
      </div>

      <FormError message={error} />

      {key === null ? (
        <Skeleton className="h-10 w-full" />
      ) : key === "missing" ? (
        <p className="text-sm text-muted-foreground">No operator key is configured.</p>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 px-3 py-2">
          <div className="flex flex-col">
            <span className="text-sm font-medium capitalize">{key.provider}</span>
            <span className="font-mono text-xs text-muted-foreground">
              {key.fingerprint} · v{key.key_version}
            </span>
          </div>
        </div>
      )}

      <div>
        <Button variant="secondary" size="sm" onClick={() => setShowRotate(true)}>
          Rotate key
        </Button>
      </div>

      <Modal
        open={showRotate}
        onClose={() => (saving ? undefined : setShowRotate(false))}
        dismissOnBackdrop={!saving}
        title="Rotate operator key"
        description="The new key replaces the shared default for every user. The old value is discarded."
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowRotate(false)} disabled={saving}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void onRotate()} loading={saving}>
              Rotate
            </Button>
          </>
        }
      >
        <MaskedSecretInput
          label="New Gemini key"
          connected={false}
          editing
          value={value}
          onChange={setValue}
          error={rotateError}
          hint="Stored encrypted; never displayed again."
          disabled={saving}
        />
      </Modal>
    </Card>
  );
}
