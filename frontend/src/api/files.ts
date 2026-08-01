import type { FileMetadata, Page } from "../types/api";
import { API_BASE_URL, isRecord, responseError } from "./client";

function isNullableString(value: unknown): value is string | null {
  return typeof value === "string" || value === null;
}

export function isFileMetadata(value: unknown): value is FileMetadata {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.thread_id === "string" &&
    isNullableString(value.source_file_id) &&
    ["upload", "parsed", "artifact"].includes(String(value.category)) &&
    typeof value.original_name === "string" &&
    isNullableString(value.extension) &&
    isNullableString(value.mime_type) &&
    typeof value.size_bytes === "number" &&
    isNullableString(value.parse_status) &&
    isNullableString(value.parse_error) &&
    isNullableString(value.parsed_file_id) &&
    typeof value.created_at === "string"
  );
}

function isFilePage(value: unknown): value is Page<FileMetadata> {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isFileMetadata) &&
    typeof value.page === "number" &&
    typeof value.page_size === "number" &&
    typeof value.total === "number"
  );
}

export async function fetchFiles(
  threadId: string,
  signal?: AbortSignal,
): Promise<Page<FileMetadata>> {
  const response = await fetch(
    `${API_BASE_URL}/api/threads/${encodeURIComponent(threadId)}/files?category=upload&page=1&page_size=100`,
    { headers: { Accept: "application/json" }, signal },
  );
  if (!response.ok) {
    throw await responseError(response);
  }
  const payload: unknown = await response.json();
  if (!isFilePage(payload)) {
    throw new Error("后端返回了无效文件数据");
  }
  return payload;
}

export async function uploadFile(
  threadId: string,
  file: File,
): Promise<FileMetadata> {
  const body = new FormData();
  body.append("file", file, file.name);
  const response = await fetch(
    `${API_BASE_URL}/api/threads/${encodeURIComponent(threadId)}/files`,
    { method: "POST", headers: { Accept: "application/json" }, body },
  );
  if (!response.ok) {
    throw await responseError(response);
  }
  const payload: unknown = await response.json();
  if (!isRecord(payload) || !isFileMetadata(payload.file)) {
    throw new Error("后端返回了无效文件数据");
  }
  return payload.file;
}

export async function deleteFile(
  threadId: string,
  fileId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/threads/${encodeURIComponent(threadId)}/files/${encodeURIComponent(fileId)}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response);
  }
}
