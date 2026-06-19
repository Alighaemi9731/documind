/**
 * Same-origin fetch client for the DocuMind API.
 *
 * Transport model (ADR-0001):
 *  - The short-lived access JWT lives ONLY in JS memory (a module-scoped
 *    variable here, surfaced to React via the auth context). It is attached as
 *    `Authorization: Bearer <token>` on every API call.
 *  - The refresh token is an httpOnly cookie the browser never exposes to JS,
 *    Path-scoped to /api/auth and attached automatically by the browser. On a
 *    401 we perform a SINGLE-FLIGHT silent refresh by POSTing same-origin to
 *    `/api/auth/refresh` (in production Caddy routes /api/* straight to the
 *    backend; `next dev` proxies via the next.config rewrite) with the
 *    double-submit `X-CSRF-Token` header read from the readable CSRF cookie,
 *    then retry the original request exactly once.
 *
 * No token is ever written to localStorage/sessionStorage.
 */

import type { ApiErrorBody, RefreshResponse } from "./types";

/** Readable CSRF cookie name (must match the backend's CSRF_COOKIE_NAME). */
const CSRF_COOKIE_NAME = "documind_csrf";

/** In-memory access token. Never persisted to storage. */
let accessToken: string | null = null;

/** Listeners notified whenever the in-memory access token changes. */
const tokenListeners = new Set<(token: string | null) => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  for (const listener of tokenListeners) {
    listener(token);
  }
}

export function onAccessTokenChange(listener: (token: string | null) => void): () => void {
  tokenListeners.add(listener);
  return () => {
    tokenListeners.delete(listener);
  };
}

/**
 * Structured API error carrying the canonical `{error:{code,message,field?}}`
 * shape (ARCHITECTURE.md §6) plus the HTTP status, so callers can branch on
 * status (401/403/409/422) and render inline field errors.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly field?: string;

  constructor(status: number, code: string, message: string, field?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let code = "error";
  let message = response.statusText || "Request failed";
  let field: string | undefined;
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      field = body.error.field;
    }
  } catch {
    // Non-JSON body (e.g. proxy error); keep the status-derived defaults.
  }
  return new ApiError(response.status, code, message, field);
}

/**
 * Single-flight silent refresh. Concurrent 401s share one in-flight refresh
 * promise so we never fire multiple refresh calls (which would rotate the
 * refresh-token family more than once and risk a false reuse-detection lockout).
 */
let refreshInFlight: Promise<boolean> | null = null;

/** Read a readable (non-httpOnly) cookie value by name. */
function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/** Double-submit CSRF header for the cookie-bearing POSTs (refresh/logout). */
function csrfHeaders(): Record<string, string> {
  const token = readCookie(CSRF_COOKIE_NAME);
  return token ? { "X-CSRF-Token": token } : {};
}

async function performRefresh(): Promise<boolean> {
  const response = await fetch("/api/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
  });
  if (!response.ok) {
    setAccessToken(null);
    return false;
  }
  const data = (await response.json()) as RefreshResponse;
  if (!data?.access_token) {
    setAccessToken(null);
    return false;
  }
  setAccessToken(data.access_token);
  return true;
}

export function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

type ApiRequestInit = Omit<RequestInit, "body"> & {
  /** JSON-serializable body; serialized and content-typed automatically. */
  json?: unknown;
  /** Raw body for non-JSON payloads (rare in Phase 1). */
  body?: BodyInit | null;
  /** When false, a 401 will not trigger the silent-refresh retry. */
  retryOnUnauthorized?: boolean;
};

async function doFetch(path: string, init: ApiRequestInit, withAuth: boolean): Promise<Response> {
  // `retryOnUnauthorized` is handled by the callers; it stays on `rest` and is
  // harmlessly ignored by `fetch`.
  const { json, body: rawBody, ...rest } = init;

  const headers = new Headers(init.headers);
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");
  if (withAuth && accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const body = json !== undefined ? JSON.stringify(json) : rawBody;

  return fetch(`/api${path}`, {
    ...rest,
    headers,
    body,
    credentials: "same-origin",
  });
}

/**
 * Perform an authenticated JSON request against `/api{path}`.
 *
 * On 401 (and when `retryOnUnauthorized` is not disabled) it runs the
 * single-flight refresh and retries the request once. Returns parsed JSON, or
 * `undefined` for 204/empty responses. Throws {@link ApiError} on non-2xx.
 */
export async function apiFetch<T = unknown>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const retryOnUnauthorized = init.retryOnUnauthorized ?? true;

  let response = await doFetch(path, init, true);

  if (response.status === 401 && retryOnUnauthorized) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await doFetch(path, init, true);
    }
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204 || response.headers.get("Content-Length") === "0") {
    return undefined as T;
  }

  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/**
 * Perform a request WITHOUT attaching the access token and without the
 * silent-refresh retry. Used for the public auth/config endpoints.
 */
export async function apiPublicFetch<T = unknown>(
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const response = await doFetch(path, { ...init, retryOnUnauthorized: false }, false);
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204 || response.headers.get("Content-Length") === "0") {
    return undefined as T;
  }
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/**
 * Log out: revoke the refresh-token family server-side (CSRF-protected) and
 * clear the in-memory access token. Best-effort — local state is cleared
 * regardless of the network outcome.
 */
export async function apiLogout(): Promise<void> {
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: csrfHeaders(),
    });
  } catch {
    // ignore — caller clears local state regardless
  }
  setAccessToken(null);
}
