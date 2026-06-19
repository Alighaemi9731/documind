/**
 * Typed admin API client over the §6 admin endpoints (ARCHITECTURE.md §6/§10).
 *
 * Every call is Bearer + admin-scoped (the backend `require_admin` chain
 * enforces the role; the auth context gates the UI). Provider/operator keys are
 * surfaced as FINGERPRINTS ONLY — this client never receives or returns secrets.
 *
 * NOTE on GET/PUT /api/admin/settings: this is a §6 endpoint. It returns the
 * install's runtime settings (registration mode, default provider, default
 * quota, branding). The shapes mirror the backend `SystemSettings` singleton +
 * `BrandingPublic`.
 */

import { apiFetch } from "./api";
import type { Branding, Provider, RegistrationMode, UserRole, UserStatus } from "./types";

// ---- Users ------------------------------------------------------------------

export interface AdminUser {
  id: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  created_at: string;
}

export interface AdminUserList {
  users: AdminUser[];
  page: number;
  total: number;
}

export interface ListUsersParams {
  q?: string;
  status?: UserStatus;
  role?: UserRole;
  page?: number;
}

function queryString(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") qs.set(key, String(value));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export function listUsers(params: ListUsersParams = {}): Promise<AdminUserList> {
  return apiFetch<AdminUserList>(`/admin/users${queryString({ ...params })}`);
}

export function disableUser(userId: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${userId}/disable`, { method: "POST" });
}

export function promoteUser(userId: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${userId}/promote`, { method: "POST" });
}

export function demoteUser(userId: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${userId}/demote`, { method: "POST" });
}

export function deleteUser(userId: string): Promise<void> {
  return apiFetch<void>(`/admin/users/${userId}`, { method: "DELETE" });
}

// ---- Registrations (approval queue) -----------------------------------------

export function pendingRegistrations(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>("/admin/registrations/pending");
}

export function approveRegistration(userId: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/registrations/${userId}/approve`, { method: "POST" });
}

export function rejectRegistration(userId: string): Promise<void> {
  return apiFetch<void>(`/admin/registrations/${userId}/reject`, { method: "POST" });
}

// ---- Invites ----------------------------------------------------------------

export interface InviteCreateInput {
  email?: string;
  role?: UserRole;
}

/** The token is returned ONCE here (copy-the-URL delivery). */
export interface InviteCreated {
  id: string;
  token: string;
  role: UserRole;
  expires_at: string;
}

export interface Invite {
  id: string;
  email: string | null;
  role: UserRole;
  expires_at: string;
  consumed_at: string | null;
}

export function createInvite(input: InviteCreateInput): Promise<InviteCreated> {
  return apiFetch<InviteCreated>("/admin/invites", { method: "POST", json: input });
}

export function listInvites(): Promise<Invite[]> {
  return apiFetch<Invite[]>("/admin/invites");
}

export function deleteInvite(inviteId: string): Promise<void> {
  return apiFetch<void>(`/admin/invites/${inviteId}`, { method: "DELETE" });
}

// ---- Usage (time-series) ----------------------------------------------------

export interface UsagePoint {
  bucket: string;
  tokens_in: number;
  tokens_out: number;
}

export interface UsageResponse {
  series: UsagePoint[];
}

export interface UsageParams {
  from?: string;
  to?: string;
  user_id?: string;
  group_by?: "day" | "month";
}

export function getUsage(params: UsageParams = {}): Promise<UsageResponse> {
  return apiFetch<UsageResponse>(`/admin/usage${queryString({ ...params })}`);
}

// ---- Per-user quota ---------------------------------------------------------

export interface Quota {
  monthly_token_limit: number | null;
  requests_per_day: number | null;
  hard_disabled: boolean;
}

export type QuotaUpdate = Partial<Quota>;

export function getQuota(userId: string): Promise<Quota> {
  return apiFetch<Quota>(`/admin/users/${userId}/quota`);
}

export function setQuota(userId: string, update: QuotaUpdate): Promise<Quota> {
  return apiFetch<Quota>(`/admin/users/${userId}/quota`, { method: "PUT", json: update });
}

// ---- Per-user key metadata (fingerprints only — NEVER secrets) --------------

export interface KeyMetadata {
  provider: Provider;
  fingerprint: string;
  valid: boolean;
  checked_at: string | null;
}

export function getUserKeys(userId: string): Promise<KeyMetadata[]> {
  return apiFetch<KeyMetadata[]>(`/admin/users/${userId}/keys`);
}

// ---- Operator default key (fingerprint only; rotate) ------------------------

export interface OperatorKey {
  provider: string;
  fingerprint: string;
  key_version: number;
}

export function getOperatorKey(): Promise<OperatorKey> {
  return apiFetch<OperatorKey>("/admin/operator-key");
}

/** Rotate the operator-default key. The plaintext is write-only (never echoed). */
export function rotateOperatorKey(apiKey: string): Promise<OperatorKey> {
  return apiFetch<OperatorKey>("/admin/operator-key", {
    method: "PUT",
    json: { api_key: apiKey },
  });
}

// ---- System settings (GET/PUT /api/admin/settings) --------------------------

export interface AdminSettings {
  registration_mode: RegistrationMode;
  default_provider: string;
  signups_enabled?: boolean;
  default_quota?: number | null;
  branding: Branding;
}

export type AdminSettingsUpdate = Partial<{
  registration_mode: RegistrationMode;
  default_provider: string;
  signups_enabled: boolean;
  default_quota: number | null;
  branding: Partial<Branding>;
}>;

export function getAdminSettings(): Promise<AdminSettings> {
  return apiFetch<AdminSettings>("/admin/settings");
}

export function updateAdminSettings(update: AdminSettingsUpdate): Promise<AdminSettings> {
  return apiFetch<AdminSettings>("/admin/settings", { method: "PUT", json: update });
}

/** Build a shareable invite URL from a one-time token (copy-the-URL delivery). */
export function inviteUrl(token: string): string {
  if (typeof window === "undefined") return `/register?invite=${encodeURIComponent(token)}`;
  return `${window.location.origin}/register?invite=${encodeURIComponent(token)}`;
}
