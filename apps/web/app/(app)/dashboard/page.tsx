"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { direction } from "@/lib/direction";
import { createProject, listProjects } from "@/lib/projects";
import type { Project } from "@/lib/types";

export default function DashboardPage() {
  const toast = useToast();
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

  function openForm() {
    setName("");
    setDescription("");
    setFieldErrors({});
    setCreateError(null);
    setShowForm(true);
  }

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
      setShowForm(false);
      toast.success("Project created.");
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
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Each project pins its own embedding model and keeps documents isolated.
          </p>
        </div>
        <Button onClick={openForm}>New project</Button>
      </div>

      {projects === null ? (
        <ProjectsSkeleton />
      ) : loadError ? (
        <Card className="flex flex-col items-start gap-3 p-6">
          <FormError message={loadError} />
          <Button variant="secondary" onClick={() => void load()}>
            Retry
          </Button>
        </Card>
      ) : projects.length === 0 ? (
        <EmptyState onCreate={openForm} />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <li key={project.id}>
              <Link
                href={`/projects/${project.id}`}
                className="block h-full rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <Card interactive className="flex h-full flex-col gap-2 p-5">
                  <h2
                    className="line-clamp-1 text-base font-semibold text-card-foreground"
                    dir={direction(project.name)}
                  >
                    {project.name}
                  </h2>
                  {project.description ? (
                    <p
                      className="line-clamp-2 text-sm text-muted-foreground"
                      dir={direction(project.description)}
                    >
                      {project.description}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground/70">No description</p>
                  )}
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={showForm}
        onClose={() => setShowForm(false)}
        title="New project"
        description="Give it a name and an optional description."
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
            <Button type="submit" form="create-project" loading={creating}>
              Create
            </Button>
          </>
        }
      >
        <form id="create-project" className="flex flex-col gap-4" onSubmit={onCreate} noValidate>
          <FormError message={createError} />
          <Input
            label="Name"
            name="name"
            required
            autoFocus
            autoDir
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={fieldErrors.name}
          />
          <Textarea
            label="Description"
            name="description"
            autoDir
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            error={fieldErrors.description}
            hint="Optional."
          />
        </form>
      </Modal>
    </div>
  );
}

function ProjectsSkeleton() {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <li key={i}>
          <Card className="p-5">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="mt-3 h-3 w-3/4" />
          </Card>
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border bg-card px-6 py-16 text-center">
      <p className="text-base font-medium text-card-foreground">No projects yet</p>
      <p className="max-w-sm text-sm text-muted-foreground">
        Create a project to upload documents and ask grounded questions over them.
      </p>
      <Button onClick={onCreate} className="mt-2">
        Create your first project
      </Button>
    </div>
  );
}
