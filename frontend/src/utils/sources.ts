import type { SourceReference } from "../types/api";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSafeWebUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function parseSources(metadata: Record<string, unknown>): SourceReference[] {
  const value = metadata.sources;
  if (!Array.isArray(value)) {
    return [];
  }
  const sources: SourceReference[] = [];
  for (const item of value) {
    if (!isRecord(item)) {
      continue;
    }
    const { title, url, snippet, source_type: sourceType } = item;
    if (
      typeof title !== "string" ||
      typeof url !== "string" ||
      typeof snippet !== "string" ||
      (sourceType !== "search" && sourceType !== "web_page") ||
      !isSafeWebUrl(url)
    ) {
      continue;
    }
    sources.push({ title, url, snippet, source_type: sourceType });
  }
  return sources;
}
