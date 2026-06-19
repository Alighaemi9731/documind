/**
 * Settings API helpers — BYOK keys + per-capability provider selection
 * (ARCHITECTURE.md §6/§9, ADR-0006/0007).
 *
 *   GET    /api/settings/keys                  → key metadata (NO secrets)
 *   POST   /api/settings/keys {provider,api_key} → write-only save → {fingerprint,valid}
 *   DELETE /api/settings/keys/{provider}
 *   GET    /api/settings/providers             → providers + per-capability selection
 *   PUT    /api/settings/providers {capability,provider,model} → 200 | 409 mismatch
 *
 * SECRETS NEVER LEAVE THE SERVER: pasted keys are sent write-only and the API
 * returns only a fingerprint + validity. This client never reads, stores, or
 * returns a key value — there is no endpoint that would expose one.
 *
 * The owner scope is derived server-side from the JWT; the client never sends an
 * owner_id.
 */

import { apiFetch } from "./api";
import type {
  Provider,
  ProviderKeyMeta,
  ProvidersResponse,
  ProviderSelectionInput,
  SaveKeyResult,
} from "./types";

/** List saved BYOK key metadata (fingerprint + validity only; never values). */
export function listKeys(): Promise<ProviderKeyMeta[]> {
  return apiFetch<ProviderKeyMeta[]>("/settings/keys");
}

/**
 * Save (or replace) a BYOK key for `provider`. Write-only: the pasted `apiKey`
 * is sent once and only a fingerprint + validity comes back. The plaintext is
 * never persisted client-side.
 */
export function saveKey(provider: Provider, apiKey: string): Promise<SaveKeyResult> {
  return apiFetch<SaveKeyResult>("/settings/keys", {
    method: "POST",
    json: { provider, api_key: apiKey },
  });
}

/** Delete the saved BYOK key for `provider` (reverts to the shared default). */
export function deleteKey(provider: Provider): Promise<void> {
  return apiFetch<void>(`/settings/keys/${provider}`, {
    method: "DELETE",
  });
}

/** Providers (capabilities + model offerings) plus the active selection. */
export function getProviders(): Promise<ProvidersResponse> {
  return apiFetch<ProvidersResponse>("/settings/providers");
}

/**
 * Set the active provider/model for a capability. Resolves 200 on success;
 * throws `ApiError` with code `capability_unsupported` or `embedding_dim_mismatch`
 * (HTTP 409) when the chosen provider/model cannot back the capability — the
 * caller surfaces these inline.
 */
export function setProviderSelection(
  capability: ProviderSelectionInput["capability"],
  provider: Provider,
  model: string,
): Promise<void> {
  return apiFetch<void>("/settings/providers", {
    method: "PUT",
    json: { capability, provider, model },
  });
}
