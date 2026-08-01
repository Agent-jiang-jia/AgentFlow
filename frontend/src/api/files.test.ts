import { afterEach, describe, expect, it, vi } from "vitest";

import type { FileMetadata } from "../types/api";
import { fetchFiles, isFileMetadata } from "./files";

const file: FileMetadata = {
  id: "file-id",
  thread_id: "thread-id",
  source_file_id: null,
  category: "upload",
  original_name: "资料.txt",
  extension: ".txt",
  mime_type: "text/plain",
  size_bytes: 12,
  parse_status: "success",
  parse_error: null,
  parsed_file_id: "parsed-id",
  created_at: "2026-08-01T00:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("file API validation", () => {
  it("accepts the complete safe metadata shape", () => {
    expect(isFileMetadata(file)).toBe(true);
    expect(isFileMetadata({ ...file, size_bytes: "12" })).toBe(false);
    expect(isFileMetadata({ ...file, stored_path: "secret", category: "other" })).toBe(
      false,
    );
  });

  it("requests only upload metadata for the current thread", async () => {
    const requestedUrls: string[] = [];
    const fetchMock = vi.fn((input: RequestInfo | URL): Promise<Response> => {
      requestedUrls.push(
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url,
      );
      return Promise.resolve(
        new Response(
          JSON.stringify({ items: [file], page: 1, page_size: 100, total: 1 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchFiles("thread/unsafe");

    expect(response.items).toEqual([file]);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(requestedUrls[0]).toContain(
      "/api/threads/thread%2Funsafe/files?category=upload",
    );
  });

  it("rejects malformed successful responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ items: [{ id: "partial" }] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );

    await expect(fetchFiles("thread-id")).rejects.toThrow("无效文件数据");
  });
});
