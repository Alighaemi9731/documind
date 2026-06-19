"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { FileDropzone } from "@/components/FileDropzone";
import { FormError } from "@/components/FormError";
import { StatusPill, isTerminalStatus, statusLabel, statusProgress } from "@/components/StatusPill";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { deleteDocument, reprocessDocument } from "@/lib/documents";
import { getProject } from "@/lib/projects";
import type { DocumentItem, Project } from "@/lib/types";
import { useDocumentStatus } from "@/lib/use-document-status";

/**
 * Project view: document list with live status pills + per-stage progress, the
 * upload dropzone, and per-document reprocess/delete actions. Status is driven
 * by the adaptive polling hook (2s while non-terminal, paused on hidden tab).
 */
export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [tab, setTab] = useState<"documents" | "chat">("documents");

  const { documents, isLoading, error, isPolling, refresh } = useDocumentStatus(projectId);

  // Chat is only useful once at least one document is ready to retrieve over.
  const hasReadyDocs = (documents ?? []).some((d) => d.status === "ready");

  // Per-document in-flight action ("reprocess" | "delete") to disable buttons.
  const [pendingAction, setPendingAction] = useState<Record<string, "reprocess" | "delete">>({});
  const [actionError, setActionError] = useState<string | null>(null);

  const loadProject = useCallback(async () => {
    setProjectError(null);
    try {
      setProject(await getProject(projectId));
    } catch (err) {
      setProjectError(err instanceof ApiError ? err.message : "Could not load this project.");
    }
  }, [projectId]);

  useEffect(() => {
    void loadProject();
  }, [loadProject]);

  const onReprocess = useCallback(
    async (doc: DocumentItem) => {
      setActionError(null);
      setPendingAction((prev) => ({ ...prev, [doc.id]: "reprocess" }));
      try {
        await reprocessDocument(projectId, doc.id);
        await refresh();
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : "Could not reprocess the document.");
      } finally {
        setPendingAction((prev) => {
          const next = { ...prev };
          delete next[doc.id];
          return next;
        });
      }
    },
    [projectId, refresh],
  );

  const onDelete = useCallback(
    async (doc: DocumentItem) => {
      setActionError(null);
      setPendingAction((prev) => ({ ...prev, [doc.id]: "delete" }));
      try {
        await deleteDocument(projectId, doc.id);
        await refresh();
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : "Could not delete the document.");
      } finally {
        setPendingAction((prev) => {
          const next = { ...prev };
          delete next[doc.id];
          return next;
        });
      }
    },
    [projectId, refresh],
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link
          href="/dashboard"
          className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:underline"
        >
          &larr; Projects
        </Link>
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            {project?.name ?? "Project"}
          </h1>
          {isPolling ? (
            <span className="text-xs text-muted-foreground" aria-live="polite">
              Updating…
            </span>
          ) : null}
        </div>
        {project?.description ? (
          <p className="text-sm text-muted-foreground">{project.description}</p>
        ) : null}
        <FormError message={projectError} className="mt-2" />
      </div>

      <div
        role="tablist"
        aria-label="Project sections"
        className="flex gap-1 border-b border-border"
      >
        <TabButton
          id="documents"
          label="Documents"
          active={tab === "documents"}
          onClick={() => setTab("documents")}
        />
        <TabButton id="chat" label="Chat" active={tab === "chat"} onClick={() => setTab("chat")} />
      </div>

      {tab === "documents" ? (
        <div
          role="tabpanel"
          id="panel-documents"
          aria-labelledby="tab-documents"
          className="flex flex-col gap-6"
        >
          <section aria-label="Upload documents">
            <FileDropzone projectId={projectId} onUploaded={() => void refresh()} />
          </section>

          <section aria-label="Documents" className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-medium text-foreground">Documents</h2>
              {documents && documents.length > 0 ? (
                <Button variant="ghost" onClick={() => void refresh()}>
                  Refresh
                </Button>
              ) : null}
            </div>

            <FormError message={actionError} />

            {isLoading ? (
              <DocumentsSkeleton />
            ) : error && (documents === null || documents.length === 0) ? (
              <div className="flex flex-col items-start gap-3 rounded-2xl border border-border bg-card p-6">
                <FormError message={error} />
                <Button variant="secondary" onClick={() => void refresh()}>
                  Retry
                </Button>
              </div>
            ) : !documents || documents.length === 0 ? (
              <EmptyDocuments />
            ) : (
              <ul className="flex flex-col gap-3">
                {documents.map((doc) => (
                  <DocumentRow
                    key={doc.id}
                    doc={doc}
                    pending={pendingAction[doc.id]}
                    onReprocess={() => void onReprocess(doc)}
                    onDelete={() => void onDelete(doc)}
                  />
                ))}
              </ul>
            )}
          </section>
        </div>
      ) : (
        <div
          role="tabpanel"
          id="panel-chat"
          aria-labelledby="tab-chat"
          className="flex flex-col gap-3"
        >
          {!hasReadyDocs ? (
            <p className="rounded-xl border border-dashed border-border bg-card px-4 py-3 text-sm text-muted-foreground">
              Upload and ingest at least one document to start asking questions. Answers are drawn
              strictly from this project&apos;s documents.
            </p>
          ) : null}
          <ChatPanel projectId={projectId} />
        </div>
      )}
    </div>
  );
}

function TabButton({
  id,
  label,
  active,
  onClick,
}: {
  id: "documents" | "chat";
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      id={`tab-${id}`}
      aria-selected={active}
      aria-controls={`panel-${id}`}
      onClick={onClick}
      className={cn(
        "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        active
          ? "border-accent text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

function DocumentRow({
  doc,
  pending,
  onReprocess,
  onDelete,
}: {
  doc: DocumentItem;
  pending?: "reprocess" | "delete";
  onReprocess: () => void;
  onDelete: () => void;
}) {
  const terminal = isTerminalStatus(doc.status);
  const progress = statusProgress(doc.status);
  // Reprocess is only meaningful from a terminal state (ready|failed).
  const canReprocess = terminal && !pending;

  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-card-foreground" title={doc.filename}>
            {doc.filename}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {doc.chunk_count != null && doc.status === "ready"
              ? `${doc.chunk_count} chunk${doc.chunk_count === 1 ? "" : "s"}`
              : doc.status_detail || statusLabel(doc.status)}
          </p>
        </div>
        <StatusPill status={doc.status} errorCode={doc.error_code} className="shrink-0" />
      </div>

      {!terminal ? (
        <div
          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          aria-label={`${statusLabel(doc.status)} progress`}
        >
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-500"
            style={{ width: `${Math.max(progress * 100, 8)}%` }}
          />
        </div>
      ) : null}

      <div className="flex items-center justify-end gap-3">
        <Button
          variant="ghost"
          onClick={onReprocess}
          disabled={!canReprocess}
          loading={pending === "reprocess"}
        >
          Reprocess
        </Button>
        <Button
          variant="secondary"
          onClick={onDelete}
          disabled={pending != null}
          loading={pending === "delete"}
        >
          Delete
        </Button>
      </div>
    </li>
  );
}

function DocumentsSkeleton() {
  return (
    <ul className="flex flex-col gap-3" aria-hidden="true">
      {[0, 1].map((i) => (
        <li key={i} className="rounded-2xl border border-border bg-card p-5">
          <div className="flex items-center justify-between">
            <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
            <div className="h-5 w-20 animate-pulse rounded-full bg-muted" />
          </div>
          <div className="mt-3 h-1.5 w-full animate-pulse rounded-full bg-muted" />
        </li>
      ))}
    </ul>
  );
}

function EmptyDocuments() {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center">
      <p className="text-sm font-medium text-card-foreground">No documents yet</p>
      <p className="max-w-sm text-sm text-muted-foreground">
        Upload PDF, DOCX, TXT, or MD files above. They are parsed, chunked, and embedded so you can
        ask grounded questions over them.
      </p>
    </div>
  );
}
