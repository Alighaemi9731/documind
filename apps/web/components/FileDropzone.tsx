"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/Button";
import { FormError } from "@/components/FormError";
import { ApiError } from "@/lib/api";
import { getAppConfig } from "@/lib/config";
import { cn } from "@/lib/cn";
import { uploadDocuments } from "@/lib/documents";
import type { DocumentUploadResult } from "@/lib/types";

/**
 * Accessible multi-file drag-and-drop + file picker (ARCHITECTURE.md §7).
 *
 * Validates extension/mime (pdf/docx/txt/md) and per-file size against
 * GET /api/config `max_upload_mb` (the same cap Caddy enforces on the body),
 * shows the selected files, and uploads via multipart FormData. The actual
 * type/size guards are re-enforced server-side; this is a fast client check.
 */

/** Accepted extensions and their canonical MIME types (best-effort). */
const ACCEPTED_EXTENSIONS = ["pdf", "docx", "txt", "md"] as const;
const ACCEPT_ATTR =
  ".pdf,.docx,.txt,.md," +
  [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
  ].join(",");

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

function isAcceptedType(file: File): boolean {
  return (ACCEPTED_EXTENSIONS as readonly string[]).includes(extensionOf(file.name));
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(0)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

interface RejectedFile {
  name: string;
  reason: string;
}

export interface FileDropzoneProps {
  projectId: string;
  /** Called after a successful upload so the parent can refresh the list. */
  onUploaded?: (results: DocumentUploadResult[]) => void;
  className?: string;
}

export function FileDropzone({ projectId, onUploaded, className }: FileDropzoneProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const [maxUploadMb, setMaxUploadMb] = useState<number | null>(null);
  const [selected, setSelected] = useState<File[]>([]);
  const [rejected, setRejected] = useState<RejectedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load the upload cap once. If config fails, we fall back to type-only checks
  // (the server re-enforces size, returning OVERSIZE) rather than blocking.
  useEffect(() => {
    let active = true;
    getAppConfig()
      .then((cfg) => {
        if (active) setMaxUploadMb(cfg.max_upload_mb);
      })
      .catch(() => {
        /* size check degrades gracefully; server still enforces the cap */
      });
    return () => {
      active = false;
    };
  }, []);

  const maxBytes = maxUploadMb != null ? maxUploadMb * 1024 * 1024 : null;

  const addFiles = useCallback(
    (incoming: FileList | File[]) => {
      setError(null);
      const accepted: File[] = [];
      const newlyRejected: RejectedFile[] = [];

      for (const file of Array.from(incoming)) {
        if (!isAcceptedType(file)) {
          newlyRejected.push({
            name: file.name,
            reason: "Unsupported type (use PDF, DOCX, TXT, MD).",
          });
          continue;
        }
        if (maxBytes != null && file.size > maxBytes) {
          newlyRejected.push({
            name: file.name,
            reason: `Too large (max ${maxUploadMb} MB).`,
          });
          continue;
        }
        accepted.push(file);
      }

      setRejected(newlyRejected);
      if (accepted.length > 0) {
        setSelected((prev) => {
          // De-dupe by name+size so re-selecting the same file is a no-op.
          const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
          const merged = [...prev];
          for (const f of accepted) {
            const key = `${f.name}:${f.size}`;
            if (!seen.has(key)) {
              merged.push(f);
              seen.add(key);
            }
          }
          return merged;
        });
      }
    },
    [maxBytes, maxUploadMb],
  );

  function onInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    if (event.target.files) {
      addFiles(event.target.files);
    }
    // Reset so selecting the same file again re-fires change.
    event.target.value = "";
  }

  function onDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragOver(false);
    if (event.dataTransfer.files?.length) {
      addFiles(event.dataTransfer.files);
    }
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      inputRef.current?.click();
    }
  }

  function removeSelected(index: number) {
    setSelected((prev) => prev.filter((_, i) => i !== index));
  }

  async function onUpload() {
    if (selected.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      const results = await uploadDocuments(projectId, selected);
      setSelected([]);
      setRejected([]);
      onUploaded?.(results);
    } catch (err) {
      if (err instanceof ApiError) {
        // 413 oversize / 415 bad type / 422 validation / 429 queue full.
        setError(err.message);
      } else {
        setError("Upload failed. Please try again.");
      }
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div
        role="button"
        tabIndex={0}
        aria-describedby={`${inputId}-hint`}
        aria-disabled={uploading || undefined}
        onClick={() => inputRef.current?.click()}
        onKeyDown={onKeyDown}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          dragOver ? "border-accent bg-accent/5" : "border-border bg-card hover:bg-muted",
        )}
      >
        <p className="text-sm font-medium text-card-foreground">
          Drag &amp; drop files here, or click to browse
        </p>
        <p id={`${inputId}-hint`} className="text-xs text-muted-foreground">
          PDF, DOCX, TXT, MD
          {maxUploadMb != null ? ` · up to ${maxUploadMb} MB each` : ""}
        </p>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          multiple
          accept={ACCEPT_ATTR}
          className="sr-only"
          onChange={onInputChange}
          aria-label="Choose files to upload"
        />
      </div>

      <FormError message={error} />

      {rejected.length > 0 ? (
        <ul className="flex flex-col gap-1" aria-label="Rejected files">
          {rejected.map((r) => (
            <li key={r.name} className="text-xs text-red-600 dark:text-red-400">
              {r.name}: {r.reason}
            </li>
          ))}
        </ul>
      ) : null}

      {selected.length > 0 ? (
        <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
          <ul className="flex flex-col gap-2" aria-label="Selected files">
            {selected.map((file, index) => (
              <li
                key={`${file.name}:${file.size}`}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="min-w-0 flex-1 truncate text-card-foreground" title={file.name}>
                  {file.name}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatBytes(file.size)}
                </span>
                <button
                  type="button"
                  onClick={() => removeSelected(index)}
                  disabled={uploading}
                  className="shrink-0 rounded text-xs text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
                  aria-label={`Remove ${file.name}`}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <div className="flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setSelected([])}
              disabled={uploading}
            >
              Clear
            </Button>
            <Button type="button" onClick={onUpload} loading={uploading}>
              Upload {selected.length} file{selected.length === 1 ? "" : "s"}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
