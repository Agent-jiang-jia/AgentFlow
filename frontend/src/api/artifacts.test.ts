import { afterEach, describe, expect, it, vi } from "vitest";

import type { FileMetadata } from "../types/api";
import {
  artifactDownloadUrl,
  fetchArtifacts,
} from "./artifacts";

const artifact: FileMetadata = {
  id: "artifact-id",
  thread_id: "thread-id",
  source_file_id: null,
  category: "artifact",
  original_name: "report.md",
  extension: ".md",
  mime_type: "text/markdown",
  size_bytes: 20,
  parse_status: null,
  parse_error: null,
  parsed_file_id: null,
  description: "研究报告",
  created_at: "2026-08-01T00:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Artifact API validation", () => {
  it("loads only complete Artifact metadata", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ items: [artifact], page: 1, page_size: 100, total: 1 }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );

    await expect(fetchArtifacts("thread-id")).resolves.toMatchObject({
      items: [artifact],
      total: 1,
    });
  });

  it("rejects upload metadata and escapes download identifiers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              items: [{ ...artifact, category: "upload" }],
              page: 1,
              page_size: 100,
              total: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );

    await expect(fetchArtifacts("thread-id")).rejects.toThrow("无效成果数据");
    expect(artifactDownloadUrl("thread/unsafe", "file?unsafe")).toContain(
      "/thread%2Funsafe/artifacts/file%3Funsafe/download",
    );
  });
});
