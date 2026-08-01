import { describe, expect, it } from "vitest";

import { parseSources } from "./sources";

describe("parseSources", () => {
  it("keeps only complete safe web references", () => {
    expect(
      parseSources({
        sources: [
          {
            title: "Fetched page",
            url: "https://example.com/article",
            snippet: "Summary",
            source_type: "web_page",
          },
          {
            title: "Unsafe",
            url: "javascript:alert(1)",
            snippet: "ignored",
            source_type: "search",
          },
          { title: "Incomplete" },
        ],
      }),
    ).toEqual([
      {
        title: "Fetched page",
        url: "https://example.com/article",
        snippet: "Summary",
        source_type: "web_page",
      },
    ]);
  });

  it("returns an empty list for malformed metadata", () => {
    expect(parseSources({ sources: "invalid" })).toEqual([]);
    expect(parseSources({})).toEqual([]);
  });
});
