/**
 * Streaming chat client for the RAG query endpoint (ARCHITECTURE.md §6/§8).
 *
 *   POST /api/projects/{id}/query  {question, stream:true}  → SSE
 *     event:token      data:{"text":"…"}        (answer deltas; sentinel pre-stripped)
 *     event:citations  data:[Citation, …]       (server-validated against retrieved set)
 *     event:done       data:{grounded, provider, usage, message_id}
 *
 * Why fetch + ReadableStream and NOT EventSource: EventSource cannot send an
 * `Authorization` header or a POST body. We therefore use `fetch` with the
 * in-memory Bearer access token from lib/api.ts, read `response.body` via a
 * reader, and parse the SSE framing ourselves. On a 401 we run the SAME
 * single-flight silent refresh as the REST client (refreshAccessToken) and
 * retry the request exactly once.
 *
 * Trust model (ADR-0008): the authoritative `grounded` flag arrives ONLY in the
 * `done` event. The server has already stripped the `<<<GROUNDED…>>>` sentinel
 * from the token stream and validated every citation against the retrieved
 * chunk-id set, so this client renders tokens/citations/grounded verbatim and
 * never scrapes grounding from token text.
 */

import { ApiError, getAccessToken, refreshAccessToken } from "./api";
import type { ApiErrorBody, Citation, ChatStreamEvent, QueryDoneEvent } from "./types";

export interface StreamQueryOptions {
  /** Abort the in-flight request (Composer "stop", unmount, navigation). */
  signal?: AbortSignal;
}

/** Build the Bearer headers from the in-memory access token. */
function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function postQuery(
  projectId: string,
  question: string,
  signal?: AbortSignal,
): Promise<Response> {
  return fetch(`/api/projects/${encodeURIComponent(projectId)}/query`, {
    method: "POST",
    credentials: "same-origin",
    headers: authHeaders(),
    body: JSON.stringify({ question, stream: true }),
    signal,
  });
}

/** Map a non-2xx response to the canonical ApiError (shared error envelope). */
async function toApiError(response: Response): Promise<ApiError> {
  let code = "error";
  let message = response.statusText || "Request failed";
  let field: string | undefined;
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      field = body.error.field;
    }
  } catch {
    // Non-JSON body; keep the status-derived defaults.
  }
  return new ApiError(response.status, code, message, field);
}

/**
 * Parse one SSE record (the text between blank-line separators) into a typed
 * stream event. Returns null for keep-alive comments or unknown event names so
 * the caller can skip them. A record is a set of `field: value` lines; we honor
 * `event:` and (possibly multi-line) `data:` per the SSE spec.
 */
function parseSseRecord(record: string): ChatStreamEvent | null {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const rawLine of record.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (line === "" || line.startsWith(":")) {
      // Blank line inside a record shouldn't happen (it delimits records), and
      // a leading ':' is a comment/keep-alive — ignore both.
      continue;
    }
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    // Per spec a single leading space after the colon is stripped.
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }
    if (field === "event") {
      eventName = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }

  const data = dataLines.join("\n");
  if (eventName === "token") {
    // Tolerate either {"text":"…"} or a bare JSON string payload.
    try {
      const parsed = JSON.parse(data);
      const text = typeof parsed === "string" ? parsed : (parsed?.text ?? "");
      return { type: "token", text: String(text) };
    } catch {
      // Some servers send raw text deltas; pass through as-is.
      return { type: "token", text: data };
    }
  }
  if (eventName === "citations") {
    try {
      const citations = JSON.parse(data) as Citation[];
      return { type: "citations", citations: Array.isArray(citations) ? citations : [] };
    } catch {
      return { type: "citations", citations: [] };
    }
  }
  if (eventName === "error") {
    try {
      const body = JSON.parse(data) as ApiErrorBody;
      return {
        type: "error",
        code: body?.error?.code ?? "error",
        message: body?.error?.message ?? "The answer service is unavailable.",
      };
    } catch {
      return { type: "error", code: "error", message: "The answer service is unavailable." };
    }
  }
  if (eventName === "done") {
    try {
      const payload = JSON.parse(data) as QueryDoneEvent;
      return {
        type: "done",
        // grounded defaults to false (fail-closed) if the field is missing.
        grounded: payload.grounded === true,
        messageId: payload.message_id ?? "",
        done: payload,
      };
    } catch {
      return {
        type: "done",
        grounded: false,
        messageId: "",
        done: { grounded: false, message_id: "" },
      };
    }
  }
  return null;
}

/**
 * Read the SSE body, splitting on the blank-line record separator and yielding
 * a typed event per record. Buffers partial records across chunk boundaries.
 */
async function* readSseStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<ChatStreamEvent, void, unknown> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Records are separated by a blank line (\n\n, tolerating \r\n\r\n).
      let sep = indexOfRecordBoundary(buffer);
      while (sep !== -1) {
        const record = buffer.slice(0, sep);
        buffer = buffer.slice(boundaryEnd(buffer, sep));
        const event = parseSseRecord(record);
        if (event) yield event;
        sep = indexOfRecordBoundary(buffer);
      }
    }
    // Flush any trailing record without a final blank line.
    const tail = (buffer + decoder.decode()).trim();
    if (tail !== "") {
      const event = parseSseRecord(tail);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}

/** Index of the start of the next record boundary (\n\n or \r\n\r\n), or -1. */
function indexOfRecordBoundary(buffer: string): number {
  const lf = buffer.indexOf("\n\n");
  const crlf = buffer.indexOf("\r\n\r\n");
  if (lf === -1) return crlf;
  if (crlf === -1) return lf;
  return Math.min(lf, crlf);
}

/** Length of the boundary marker at `start` so we can slice past it. */
function boundaryEnd(buffer: string, start: number): number {
  return buffer.startsWith("\r\n\r\n", start) ? start + 4 : start + 2;
}

/**
 * Stream an answer for `question` over the project's RAG query endpoint.
 *
 * Yields a sequence of {@link ChatStreamEvent}: zero-or-more `token` deltas,
 * then a single `citations` event, then a terminal `done` event carrying the
 * authoritative `grounded` flag and durable `message_id` (ADR-0017). Throws
 * {@link ApiError} on a non-2xx response (e.g. 429 quota, 403 isolation).
 *
 * On a 401 it performs the shared single-flight refresh and retries once.
 */
export async function* streamQuery(
  projectId: string,
  question: string,
  options: StreamQueryOptions = {},
): AsyncGenerator<ChatStreamEvent, void, unknown> {
  const { signal } = options;

  let response = await postQuery(projectId, question, signal);
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await postQuery(projectId, question, signal);
    }
  }

  if (!response.ok) {
    throw await toApiError(response);
  }
  if (!response.body) {
    throw new ApiError(response.status, "no_stream", "The response had no readable body.");
  }

  yield* readSseStream(response.body);
}
