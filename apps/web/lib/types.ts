/**
 * Frontend mirror of the canonical enums and REST response shapes
 * (ARCHITECTURE.md §6, ADR-0013). This file is the single TypeScript source of
 * truth and must not drift from the backend enums / API table.
 */

// ---- Canonical enums (ADR-0013) ---------------------------------------------

export type UserRole = "user" | "admin";
export type UserStatus = "active" | "pending" | "disabled";
export type RegistrationMode = "open" | "approval" | "invite";
export type Provider = "openai" | "anthropic" | "google" | "groq" | "local_bge_m3";
export type Capability = "chat" | "embedding";
export type KeySource = "shared" | "byok";
export type DocumentStatus = "queued" | "parsing" | "chunking" | "embedding" | "ready" | "failed";

// ---- Error shape (ARCHITECTURE.md §6) ---------------------------------------

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    field?: string;
  };
}

// ---- Auth payloads ----------------------------------------------------------

/** GET /api/auth/me */
export interface CurrentUser {
  id: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  active_provider?: string | null;
  has_byok?: Record<string, boolean>;
  quota?: {
    used: number;
    limit: number | null;
  };
}

/** POST /api/auth/login → 200 */
export interface LoginResponse {
  access_token: string;
  expires_in: number;
  user: CurrentUser;
}

/**
 * POST /api/auth/register
 *  - open  → 201 with access_token (auto-login)
 *  - approval → 202 `{status:"pending"}`
 *  - invite → 201 (valid token) or 403
 */
export interface RegisterResponse {
  access_token?: string;
  expires_in?: number;
  user?: CurrentUser;
  status?: "pending";
}

/** Response surfaced by the Next route handler proxy for /api/auth/refresh. */
export interface RefreshResponse {
  access_token: string;
  expires_in?: number;
}

// ---- Config -----------------------------------------------------------------

/** GET /api/config */
export interface AppConfig {
  max_upload_mb: number;
  registration_mode: RegistrationMode;
}

// ---- Projects ---------------------------------------------------------------

/** Item in GET /api/projects */
export interface Project {
  id: string;
  name: string;
  description?: string | null;
  embedding_provider?: Provider;
  embedding_model?: string;
  embedding_dim?: number;
  created_at: string;
}

/** POST /api/projects body */
export interface CreateProjectInput {
  name: string;
  description?: string;
}

// ---- Documents (ARCHITECTURE.md §6/§7, ADR-0013) ----------------------------

/**
 * Typed error codes a failed document carries (ADR-0013). Kept as a union so the
 * UI can render a human reason; an unrecognized code falls back to a generic
 * message rather than throwing.
 */
export type DocumentErrorCode =
  | "OVERSIZE"
  | "BAD_TYPE"
  | "DECOMPRESSION_BOMB"
  | "ENCRYPTED_PDF"
  | "NO_TEXT"
  | "PARSE_ERROR"
  | "EMBED_ERROR"
  | "TOO_MANY_CHUNKS";

/**
 * A document as returned by GET /api/projects/{id}/documents (poll target). The
 * non-terminal stages drive the live status pill + per-stage progress; `failed`
 * carries an `error_code` reason. Optional fields tolerate a backend that omits
 * them while a document is still queued.
 */
export interface DocumentItem {
  id: string;
  filename: string;
  mime?: string | null;
  size_bytes?: number | null;
  page_count?: number | null;
  status: DocumentStatus;
  status_detail?: string | null;
  error_code?: DocumentErrorCode | string | null;
  chunk_count?: number | null;
  embedding_model?: string | null;
  embedding_dim?: number | null;
  created_at: string;
  updated_at?: string | null;
}

/**
 * Per-file result from POST /api/projects/{id}/documents (201). `dedupe` is true
 * when the upload matched an existing document by (project_id, sha256).
 */
export interface DocumentUploadResult {
  filename: string;
  document_id: string;
  status: DocumentStatus;
  dedupe?: boolean;
}

// ---- Chat / RAG query (ARCHITECTURE.md §6/§8, ADR-0008/0017) -----------------

/**
 * Canonical citation shape (ARCHITECTURE.md §6). Emitted in the SSE
 * `citations` event and in the JSON fallback. The server has already validated
 * every citation against the exact retrieved chunk-id set for the request
 * (ADR-0008), so the client renders these as-is.
 */
export interface Citation {
  chunk_id: string;
  document_id: string;
  filename: string;
  /** 1-based page when known; null for formats without pages (e.g. plain text). */
  page: number | null;
  section_path: string | null;
  chunk_index: number;
  score: number;
  snippet: string;
}

/**
 * The authoritative `done` event (ARCHITECTURE.md §6/§8). `grounded` is the ONLY
 * trustworthy grounding signal — the client must render the grounded/refusal
 * state from this field, never by scraping the token stream (the server strips
 * the `<<<GROUNDED…>>>` sentinel before forwarding). `grounded=false` means the
 * answer is the localized "not in your documents" refusal.
 */
export interface QueryDoneEvent {
  grounded: boolean;
  provider?: string;
  usage?: {
    input_tokens: number;
    output_tokens: number;
  };
  message_id: string;
}

/**
 * POST /api/projects/{id}/query JSON fallback (identical content to the stream,
 * ARCHITECTURE.md §6). Used when streaming is unavailable; retrieval is
 * idempotent so the citations reproduce the streamed set.
 */
export interface QueryJsonResponse {
  answer: string;
  citations: Citation[];
  grounded: boolean;
  used_chunks?: number;
  provider?: string;
  message_id: string;
}

/**
 * Discriminated union yielded by the streaming chat client (lib/chat.ts) as it
 * parses the SSE `token` / `citations` / `done` events.
 */
export type ChatStreamEvent =
  | { type: "token"; text: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "done"; grounded: boolean; messageId: string; done: QueryDoneEvent }
  | { type: "error"; code: string; message: string };

// ---- Settings / BYOK & providers (ARCHITECTURE.md §6/§9, ADR-0006/0007) -----

/**
 * One model a provider offers for a capability, mirroring the backend
 * `ModelSpec` (ARCHITECTURE.md §9). `dim`/`normalized` are only meaningful for
 * embedding models (chat models report `dim: 0`); `dim` is what drives the
 * embedding_dim_mismatch guard on selection.
 */
export interface ModelInfo {
  model: string;
  dim?: number;
  normalized?: boolean;
  max_input_tokens?: number;
}

/**
 * A provider as surfaced by GET /api/settings/providers — the declarative
 * `ProviderSpec` (single source of truth, ARCHITECTURE.md §9) projected to the
 * client. Carries NO secrets: only capabilities, model offerings, and whether a
 * BYOK key is required to use it. `requires_byok=false` providers (Gemini) work
 * out of the box on the shared operator default key.
 */
export interface ProviderInfo {
  /** Provider enum value, e.g. "openai" | "anthropic" | "google" | "groq". */
  id: Provider;
  label: string;
  capabilities: Capability[];
  chat?: ModelInfo | null;
  embedding?: ModelInfo | null;
  /** When true the provider only works with a user-supplied BYOK key. */
  requires_byok: boolean;
  /** Optional UI hint for the expected key format (e.g. "sk-..."). */
  key_format_hint?: string | null;
}

/**
 * Non-secret metadata for a saved BYOK key (GET /api/settings/keys). The value
 * is NEVER returned by the API — only a `fingerprint` (last-4 + sha256 prefix),
 * a `valid` health-check result, and when it was last checked. `valid` is null
 * when the key has not yet been validated.
 */
export interface ProviderKeyMeta {
  provider: Provider;
  fingerprint: string;
  valid: boolean | null;
  checked_at?: string | null;
}

/**
 * Result of POST /api/settings/keys (write-only key save). Returns only the
 * fingerprint + validity of the freshly saved key — never the value.
 */
export interface SaveKeyResult {
  provider?: Provider;
  fingerprint: string;
  valid: boolean | null;
}

/**
 * The active per-capability provider/model selection, returned alongside the
 * provider list by GET /api/settings/providers. A capability may be absent when
 * the user is on the shared operator default for it.
 */
export interface CapabilitySelection {
  capability: Capability;
  provider: Provider;
  model: string;
  /** "byok" when a user key backs this selection, "shared" for the default. */
  key_source?: KeySource;
}

/** Full payload of GET /api/settings/providers. */
export interface ProvidersResponse {
  providers: ProviderInfo[];
  selection: CapabilitySelection[];
}

/** PUT /api/settings/providers body. */
export interface ProviderSelectionInput {
  capability: Capability;
  provider: Provider;
  model: string;
}
