/**
 * Documents API helpers (ARCHITECTURE.md §6/§7).
 *
 *   GET    /api/projects/{id}/documents              → list (poll target)
 *   POST   /api/projects/{id}/documents              → multipart 1..n upload
 *   POST   /api/projects/{id}/documents/{doc}/reprocess
 *   DELETE /api/projects/{id}/documents/{doc}        → cascade chunks
 *
 * The owner scope is derived server-side from the JWT; the client never sends an
 * owner_id. `project_id` comes from the path.
 */

import { apiFetch } from "./api";
import type { DocumentItem, DocumentUploadResult } from "./types";

/** List the project's documents (newest-first ordering is the backend's). */
export function listDocuments(projectId: string): Promise<DocumentItem[]> {
  return apiFetch<DocumentItem[]>(`/projects/${projectId}/documents`);
}

/**
 * Upload one or more files as multipart/form-data. The browser MUST set the
 * `Content-Type: multipart/form-data; boundary=...` header itself — passing a
 * `FormData` body and NOT setting Content-Type lets fetch compute the boundary.
 * Each file is appended under the `files` field (repeated for 1..n).
 */
export function uploadDocuments(projectId: string, files: File[]): Promise<DocumentUploadResult[]> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  return apiFetch<DocumentUploadResult[]>(`/projects/${projectId}/documents`, {
    method: "POST",
    body: form,
    // Deliberately no Content-Type: fetch sets the multipart boundary.
  });
}

/** Re-queue a document for ingestion (delete-then-insert of its chunks). */
export function reprocessDocument(projectId: string, documentId: string): Promise<DocumentItem> {
  return apiFetch<DocumentItem>(`/projects/${projectId}/documents/${documentId}/reprocess`, {
    method: "POST",
  });
}

/** Delete a document (cascades its chunks). Returns void (204). */
export function deleteDocument(projectId: string, documentId: string): Promise<void> {
  return apiFetch<void>(`/projects/${projectId}/documents/${documentId}`, {
    method: "DELETE",
  });
}
