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
