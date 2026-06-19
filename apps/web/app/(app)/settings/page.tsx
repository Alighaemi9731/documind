"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { FormError } from "@/components/FormError";
import { ProviderKeyRow } from "@/components/settings/ProviderKeyRow";
import { ProviderSelect } from "@/components/settings/ProviderSelect";
import { ApiError } from "@/lib/api";
import { getProviders, listKeys } from "@/lib/settings";
import type { Capability, CapabilitySelection, ProviderInfo, ProviderKeyMeta } from "@/lib/types";

/**
 * BYOK + providers settings screen (ARCHITECTURE.md §6/§9, ADR-0006/0007).
 *
 * Lists every provider with a write-only masked key row (Gemini works on the
 * shared default; a BYOK key overrides it), plus the per-capability chat /
 * embedding provider+model selection. Secrets are never displayed — only
 * fingerprints + validity. Loading / empty / error states are all handled.
 */
export default function SettingsPage() {
  const [providers, setProviders] = useState<ProviderInfo[] | null>(null);
  const [selection, setSelection] = useState<CapabilitySelection[]>([]);
  const [keys, setKeys] = useState<ProviderKeyMeta[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [providersResponse, keyList] = await Promise.all([getProviders(), listKeys()]);
      setProviders(providersResponse.providers ?? []);
      setSelection(providersResponse.selection ?? []);
      setKeys(keyList ?? []);
    } catch (err) {
      setProviders([]);
      setLoadError(
        err instanceof ApiError ? err.message : "Could not load your settings. Please retry.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Refresh only the lightweight state after a key/selection change so the row
  // badges + validity + selection readiness all stay in sync.
  const refresh = useCallback(async () => {
    try {
      const [providersResponse, keyList] = await Promise.all([getProviders(), listKeys()]);
      setProviders(providersResponse.providers ?? []);
      setSelection(providersResponse.selection ?? []);
      setKeys(keyList ?? []);
    } catch {
      // Keep the current view; a hard failure surfaces on the next full load.
    }
  }, []);

  const keysByProvider = useMemo(() => new Map(keys.map((k) => [k.provider, k])), [keys]);

  const selectionByCapability = useMemo(() => {
    const map = new Map<Capability, CapabilitySelection>();
    for (const sel of selection) {
      map.set(sel.capability, sel);
    }
    return map;
  }, [selection]);

  // A provider is "ready" for selection when it can serve a capability: either a
  // BYOK key is connected, or it runs on the shared default (requires_byok=false).
  const isProviderReady = useCallback(
    (provider: ProviderInfo): boolean => keysByProvider.has(provider.id) || !provider.requires_byok,
    [keysByProvider],
  );

  if (loading && providers === null) {
    return (
      <div className="flex flex-col gap-6">
        <Header />
        <SettingsSkeleton />
      </div>
    );
  }

  if (loadError && (providers === null || providers.length === 0)) {
    return (
      <div className="flex flex-col gap-6">
        <Header />
        <div className="flex flex-col items-start gap-3 rounded-2xl border border-border bg-card p-6">
          <FormError message={loadError} />
          <Button variant="secondary" onClick={() => void load()}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const all = providers ?? [];
  const chatProviders = all.filter((p) => p.capabilities.includes("chat"));
  const embeddingProviders = all.filter((p) => p.capabilities.includes("embedding"));

  return (
    <div className="flex flex-col gap-8">
      <Header />

      {all.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center text-sm text-muted-foreground">
          No providers are configured.
        </div>
      ) : (
        <>
          <section className="flex flex-col gap-4" aria-labelledby="byok-heading">
            <div className="flex flex-col gap-1">
              <h2 id="byok-heading" className="text-lg font-semibold text-foreground">
                Provider keys
              </h2>
              <p className="text-sm text-muted-foreground">
                Bring your own API keys. Keys are encrypted at rest and never shown again — only a
                fingerprint is displayed. Google Gemini works out of the box on the shared default;
                adding a Gemini key overrides it.
              </p>
            </div>
            <div className="flex flex-col gap-3">
              {all.map((provider) => (
                <ProviderKeyRow
                  key={provider.id}
                  provider={provider}
                  keyMeta={keysByProvider.get(provider.id) ?? null}
                  onChanged={() => void refresh()}
                />
              ))}
            </div>
          </section>

          <section className="flex flex-col gap-4" aria-labelledby="selection-heading">
            <div className="flex flex-col gap-1">
              <h2 id="selection-heading" className="text-lg font-semibold text-foreground">
                Active models
              </h2>
              <p className="text-sm text-muted-foreground">
                Choose which provider answers chat questions and which embeds your documents.
                Selections are independent — you can chat with one provider and embed with another.
              </p>
            </div>

            <div className="flex flex-col gap-5 rounded-2xl border border-border bg-card p-5">
              <ProviderSelect
                capability="chat"
                providers={chatProviders}
                selection={selectionByCapability.get("chat") ?? null}
                isProviderReady={isProviderReady}
                onChanged={() => void refresh()}
              />
              <div className="h-px bg-border" aria-hidden="true" />
              <ProviderSelect
                capability="embedding"
                providers={embeddingProviders}
                selection={selectionByCapability.get("embedding") ?? null}
                isProviderReady={isProviderReady}
                onChanged={() => void refresh()}
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Header() {
  return (
    <div className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Settings</h1>
      <p className="text-sm text-muted-foreground">Manage your provider keys and active models.</p>
    </div>
  );
}

function SettingsSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="rounded-2xl border border-border bg-card p-5">
          <div className="h-4 w-1/4 animate-pulse rounded bg-muted" />
          <div className="mt-3 h-9 w-full animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}
