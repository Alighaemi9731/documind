"use client";

import { useId, useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { setProviderSelection } from "@/lib/settings";
import type {
  Capability,
  CapabilitySelection,
  ModelInfo,
  Provider,
  ProviderInfo,
} from "@/lib/types";

/**
 * Per-capability provider + model selector (ARCHITECTURE.md §6/§9).
 *
 * Resolution is per-capability and independent: a BYOK chat provider can coexist
 * with shared Gemini embeddings. This control PUTs {capability,provider,model}
 * and surfaces the two contract errors inline:
 *   - `capability_unsupported`   — provider/model can't serve this capability
 *   - `embedding_dim_mismatch`   — 409 when the embedding dim differs from the
 *                                   project pin (cross-dim switch needs re-embed)
 */
export interface ProviderSelectProps {
  capability: Capability;
  /** Only providers that declare this capability (caller-filtered or not). */
  providers: ProviderInfo[];
  /** The current active selection for this capability, if any. */
  selection: CapabilitySelection | null;
  /** Whether each provider has a usable key (BYOK saved or shared default). */
  isProviderReady: (provider: ProviderInfo) => boolean;
  onChanged: () => void;
}

const CAPABILITY_LABEL: Record<Capability, string> = {
  chat: "Chat model",
  embedding: "Embedding model",
};

/** The ModelInfo a provider offers for a capability (chat vs embedding slot). */
function modelFor(provider: ProviderInfo, capability: Capability): ModelInfo | null {
  return (capability === "chat" ? provider.chat : provider.embedding) ?? null;
}

/** Map the contract error codes to human copy; everything else falls through. */
function selectionErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "embedding_dim_mismatch") {
      return "This embedding model's dimension differs from your project's pinned dimension. Switching requires re-embedding your documents.";
    }
    if (err.code === "capability_unsupported") {
      return "This provider does not support that capability.";
    }
    return err.message;
  }
  return "Could not update the selection. Please try again.";
}

export function ProviderSelect({
  capability,
  providers,
  selection,
  isProviderReady,
  onChanged,
}: ProviderSelectProps) {
  const selectId = useId();
  const errorId = `${selectId}-error`;

  // Providers that actually offer this capability.
  const eligible = useMemo(
    () => providers.filter((p) => modelFor(p, capability) !== null),
    [providers, capability],
  );

  const [provider, setProvider] = useState<Provider | "">(selection?.provider ?? "");
  const [model, setModel] = useState<string>(selection?.model ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedProvider = eligible.find((p) => p.id === provider) ?? null;
  const selectedModel = selectedProvider ? modelFor(selectedProvider, capability) : null;

  const ready = selectedProvider ? isProviderReady(selectedProvider) : false;
  const dirty =
    provider !== "" &&
    model !== "" &&
    (provider !== selection?.provider || model !== selection?.model);

  function onProviderChange(next: Provider | "") {
    setProvider(next);
    setError(null);
    const p = eligible.find((x) => x.id === next) ?? null;
    // Each provider exposes exactly one model per capability in the spec; pin it.
    setModel(p ? (modelFor(p, capability)?.model ?? "") : "");
  }

  async function onApply() {
    if (!provider || !model) {
      setError("Choose a provider first.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await setProviderSelection(capability, provider, model);
      onChanged();
    } catch (err) {
      setError(selectionErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={selectId} className="text-sm font-medium text-foreground">
        {CAPABILITY_LABEL[capability]}
      </label>

      <div className="flex flex-wrap items-end gap-2">
        <select
          id={selectId}
          value={provider}
          disabled={saving || eligible.length === 0}
          onChange={(e) => onProviderChange(e.target.value as Provider | "")}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={cn(
            "min-w-48 flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground",
            "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/40",
            "disabled:cursor-not-allowed disabled:opacity-60",
            error && "border-red-500 focus:border-red-500 focus:ring-red-500/40",
          )}
        >
          <option value="">Select a provider…</option>
          {eligible.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
              {modelFor(p, capability)?.model ? ` — ${modelFor(p, capability)?.model}` : ""}
            </option>
          ))}
        </select>

        <Button onClick={onApply} loading={saving} disabled={!dirty || !ready}>
          Apply
        </Button>
      </div>

      {selectedModel && selectedModel.dim ? (
        <p className="text-xs text-muted-foreground">
          {selectedModel.model} · {selectedModel.dim} dim
          {selectedModel.normalized ? " · normalized" : ""}
        </p>
      ) : selectedModel ? (
        <p className="text-xs text-muted-foreground">{selectedModel.model}</p>
      ) : null}

      {selectedProvider && !ready ? (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Add a {selectedProvider.label} API key above to use this provider.
        </p>
      ) : null}

      {error ? (
        <p id={errorId} className="text-xs text-red-500" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
