"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { deleteKey, saveKey } from "@/lib/settings";
import type { ProviderInfo, ProviderKeyMeta, SaveKeyResult } from "@/lib/types";

import { MaskedSecretInput } from "./MaskedSecretInput";

/**
 * One provider's BYOK key row (ARCHITECTURE.md §6/§9, §14).
 *
 * Shows the provider label, a connected/not-set badge with the stored key's
 * fingerprint (never the value), a write-only paste-to-save flow with validate
 * feedback, and a delete action. On save the pasted value is sent once and then
 * cleared from local state; the API returns only a fingerprint + validity.
 *
 * Providers that work on the shared default (requires_byok=false, e.g. Gemini)
 * show that BYOK is optional and overrides the shared key; required providers
 * show that a key is needed to use them at all.
 */
export interface ProviderKeyRowProps {
  provider: ProviderInfo;
  /** Saved key metadata for this provider, or null when none is stored. */
  keyMeta: ProviderKeyMeta | null;
  /** Called after a successful save/delete so the parent can refresh state. */
  onChanged: () => void;
}

function validityNote(valid: boolean | null | undefined): {
  text: string;
  tone: "ok" | "warn" | "muted";
} {
  if (valid === true) return { text: "Validated", tone: "ok" };
  if (valid === false) return { text: "Key failed validation", tone: "warn" };
  return { text: "Not yet validated", tone: "muted" };
}

export function ProviderKeyRow({ provider, keyMeta, onChanged }: ProviderKeyRowProps) {
  const connected = keyMeta !== null;

  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Fresh save feedback (fingerprint/validity from POST), shown until refresh.
  const [justSaved, setJustSaved] = useState<SaveKeyResult | null>(null);

  const fingerprint = justSaved?.fingerprint ?? keyMeta?.fingerprint ?? null;
  const valid = justSaved ? justSaved.valid : keyMeta?.valid;

  function startEditing() {
    setEditing(true);
    setError(null);
    setJustSaved(null);
    setValue("");
  }

  function cancelEditing() {
    setEditing(false);
    setError(null);
    setValue(""); // never retain the typed secret
  }

  async function onSave() {
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Paste a key to save.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await saveKey(provider.id, trimmed);
      setValue(""); // drop the plaintext immediately
      setEditing(false);
      setJustSaved(result);
      onChanged();
    } catch (err) {
      // Generic failure shape — never echo a provider error body (no oracle).
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not save the key. Check the value and try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteKey(provider.id);
      setJustSaved(null);
      setValue("");
      setEditing(false);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the key. Try again.");
    } finally {
      setDeleting(false);
    }
  }

  const note = validityNote(valid);
  const formatHint = provider.key_format_hint ?? undefined;

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-base font-medium text-card-foreground">{provider.label}</span>
          <ConnectionBadge connected={connected} requiresByok={provider.requires_byok} />
        </div>

        {!editing ? (
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={startEditing}>
              {connected ? "Replace key" : "Add key"}
            </Button>
            {connected ? (
              <Button variant="ghost" onClick={onDelete} loading={deleting} disabled={saving}>
                Delete
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      {editing ? (
        <div className="flex flex-col gap-3">
          <MaskedSecretInput
            label={`${provider.label} API key`}
            connected={connected}
            fingerprint={fingerprint}
            editing
            value={value}
            onChange={setValue}
            error={error}
            hint={formatHint ? `Format: ${formatHint}` : "Stored encrypted; never displayed."}
            disabled={saving}
          />
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={cancelEditing} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={onSave} loading={saving}>
              Save key
            </Button>
          </div>
        </div>
      ) : connected ? (
        <div className="flex flex-col gap-2">
          <MaskedSecretInput
            label={`${provider.label} API key`}
            connected
            fingerprint={fingerprint}
            editing={false}
            value=""
            onChange={() => {}}
          />
          <p
            className={cn(
              "text-xs",
              note.tone === "ok" && "text-green-600 dark:text-green-400",
              note.tone === "warn" && "text-amber-600 dark:text-amber-400",
              note.tone === "muted" && "text-muted-foreground",
            )}
            role={note.tone === "warn" ? "alert" : undefined}
          >
            {note.text}
          </p>
          {error ? (
            <p className="text-xs text-red-500" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          {provider.requires_byok
            ? "Add your API key to enable this provider."
            : "Optional — add a key to use your own account instead of the shared default."}
        </p>
      )}
    </div>
  );
}

function ConnectionBadge({
  connected,
  requiresByok,
}: {
  connected: boolean;
  requiresByok: boolean;
}) {
  if (connected) {
    return (
      <span
        className="inline-flex w-fit items-center gap-1.5 rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-0.5 text-xs font-medium text-green-700 dark:text-green-400"
        role="status"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
        Connected
      </span>
    );
  }
  if (!requiresByok) {
    return (
      <span
        className="inline-flex w-fit items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground"
        role="status"
      >
        Using shared default
      </span>
    );
  }
  return (
    <span
      className="inline-flex w-fit items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground"
      role="status"
    >
      Not set
    </span>
  );
}
