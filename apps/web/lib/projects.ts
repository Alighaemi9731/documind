/**
 * Projects API helpers (ARCHITECTURE.md §6).
 *
 *   GET  /api/projects          → list owner's projects
 *   POST /api/projects {name,description?}
 *
 * The owner scope is derived server-side from the JWT; the client never sends
 * an owner_id.
 */

import { apiFetch } from "./api";
import type { CreateProjectInput, Project } from "./types";

export function listProjects(): Promise<Project[]> {
  return apiFetch<Project[]>("/projects");
}

export function getProject(projectId: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`);
}

export function createProject(input: CreateProjectInput): Promise<Project> {
  return apiFetch<Project>("/projects", {
    method: "POST",
    json: input,
  });
}
