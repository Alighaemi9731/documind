"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { FormError } from "@/components/FormError";
import { Input } from "@/components/Input";
import { ApiError } from "@/lib/api";
import { createProject, listProjects } from "@/lib/projects";
import type { Project } from "@/lib/types";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      setProjects(await listProjects());
    } catch (err) {
      setProjects([]);
      setLoadError(
        err instanceof ApiError ? err.message : "Could not load your projects. Please retry.",
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFieldErrors({});
    setCreateError(null);
    setCreating(true);
    try {
      const project = await createProject({
        name,
        description: description.trim() ? description.trim() : undefined,
      });
      setProjects((prev) => (prev ? [project, ...prev] : [project]));
      setName("");
      setDescription("");
      setShowForm(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && err.field) {
        setFieldErrors({ [err.field]: err.message });
      } else if (err instanceof ApiError) {
        setCreateError(err.message);
      } else {
        setCreateError("Could not create the project. Please try again.");
      }
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Projects</h1>
        {!showForm ? <Button onClick={() => setShowForm(true)}>New project</Button> : null}
      </div>

      {showForm ? (
        <form
          className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-6"
          onSubmit={onCreate}
          noValidate
        >
          <FormError message={createError} />
          <Input
            label="Name"
            name="name"
            required
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={fieldErrors.name}
          />
          <Input
            label="Description"
            name="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            error={fieldErrors.description}
            hint="Optional."
          />
          <div className="flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setShowForm(false);
                setFieldErrors({});
                setCreateError(null);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" loading={creating}>
              Create
            </Button>
          </div>
        </form>
      ) : null}

      {projects === null ? (
        <ProjectsSkeleton />
      ) : loadError ? (
        <div className="flex flex-col items-start gap-3 rounded-2xl border border-border bg-card p-6">
          <FormError message={loadError} />
          <Button variant="secondary" onClick={() => void load()}>
            Retry
          </Button>
        </div>
      ) : projects.length === 0 ? (
        <EmptyState onCreate={() => setShowForm(true)} hidden={showForm} />
      ) : (
        <ul className="flex flex-col gap-3">
          {projects.map((project) => (
            <li
              key={project.id}
              className="rounded-2xl border border-border bg-card p-5 transition-colors hover:bg-muted"
            >
              <h2 className="text-base font-medium text-card-foreground">{project.name}</h2>
              {project.description ? (
                <p className="mt-1 text-sm text-muted-foreground">{project.description}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ProjectsSkeleton() {
  return (
    <ul className="flex flex-col gap-3" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <li key={i} className="rounded-2xl border border-border bg-card p-5">
          <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
          <div className="mt-3 h-3 w-2/3 animate-pulse rounded bg-muted" />
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ onCreate, hidden }: { onCreate: () => void; hidden: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center">
      <p className="text-sm font-medium text-card-foreground">No projects yet</p>
      <p className="max-w-sm text-sm text-muted-foreground">
        Create a project to upload documents and ask grounded questions over them.
      </p>
      {!hidden ? (
        <Button onClick={onCreate} className="mt-2">
          Create your first project
        </Button>
      ) : null}
    </div>
  );
}
