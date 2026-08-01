import type { FileMetadata, Page } from "../types/api";
import { API_BASE_URL, isRecord, responseError } from "./client";
import { isFileMetadata } from "./files";

function isArtifactPage(value: unknown): value is Page<FileMetadata> {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(
      (item) => isFileMetadata(item) && item.category === "artifact",
    ) &&
    typeof value.page === "number" &&
    typeof value.page_size === "number" &&
    typeof value.total === "number"
  );
}

export async function fetchArtifacts(
  threadId: string,
  signal?: AbortSignal,
): Promise<Page<FileMetadata>> {
  const response = await fetch(
    `${API_BASE_URL}/api/threads/${encodeURIComponent(threadId)}/artifacts?page=1&page_size=100`,
    { headers: { Accept: "application/json" }, signal },
  );
  if (!response.ok) {
    throw await responseError(response);
  }
  const payload: unknown = await response.json();
  if (!isArtifactPage(payload)) {
    throw new Error("后端返回了无效成果数据");
  }
  return payload;
}

export async function fetchArtifactText(
  threadId: string,
  fileId: string,
  signal?: AbortSignal,
): Promise<string> {
  const response = await fetch(artifactPreviewUrl(threadId, fileId), {
    headers: { Accept: "text/plain, text/markdown, application/json, text/csv" },
    signal,
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.text();
}

export function artifactPreviewUrl(threadId: string, fileId: string): string {
  return `${API_BASE_URL}/api/threads/${encodeURIComponent(threadId)}/artifacts/${encodeURIComponent(fileId)}/preview`;
}

export function artifactDownloadUrl(threadId: string, fileId: string): string {
  return `${API_BASE_URL}/api/threads/${encodeURIComponent(threadId)}/artifacts/${encodeURIComponent(fileId)}/download`;
}
