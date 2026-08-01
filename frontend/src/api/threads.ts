import type { Message, Page, ThreadSummary } from "../types/api";
import { API_BASE_URL, isRecord, responseError } from "./client";

function isThread(value: unknown): value is ThreadSummary {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.status === "string" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
}

function isMessage(value: unknown): value is Message {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.thread_id === "string" &&
    (typeof value.run_id === "string" || value.run_id === null) &&
    ["user", "assistant", "tool", "system"].includes(String(value.role)) &&
    typeof value.content === "string" &&
    ["text", "tool_call", "tool_result", "error"].includes(
      String(value.message_type),
    ) &&
    isRecord(value.metadata) &&
    typeof value.sequence_number === "number" &&
    typeof value.created_at === "string"
  );
}

function isPage<T>(
  value: unknown,
  itemGuard: (item: unknown) => item is T,
): value is Page<T> {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    return false;
  }
  return (
    value.items.every(itemGuard) &&
    typeof value.page === "number" &&
    typeof value.page_size === "number" &&
    typeof value.total === "number"
  );
}

async function jsonRequest<T>(
  path: string,
  guard: (value: unknown) => value is T,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  const payload: unknown = await response.json();
  if (!guard(payload)) {
    throw new Error("后端返回了无效数据");
  }
  return payload;
}

export function fetchThreads(signal?: AbortSignal): Promise<Page<ThreadSummary>> {
  return jsonRequest(
    "/api/threads?page=1&page_size=100",
    (value): value is Page<ThreadSummary> => isPage(value, isThread),
    { signal },
  );
}

export function fetchMessages(
  threadId: string,
  signal?: AbortSignal,
): Promise<Page<Message>> {
  return jsonRequest(
    `/api/threads/${encodeURIComponent(threadId)}/messages?page=1&page_size=100`,
    (value): value is Page<Message> => isPage(value, isMessage),
    { signal },
  );
}

export function createThread(title?: string): Promise<ThreadSummary> {
  return jsonRequest("/api/threads", isThread, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: title === undefined ? undefined : JSON.stringify({ title }),
  });
}

export async function deleteThread(threadId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/threads/${encodeURIComponent(threadId)}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response);
  }
}
