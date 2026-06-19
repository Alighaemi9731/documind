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
