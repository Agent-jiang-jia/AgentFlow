import { describe, expect, it } from "vitest";

import { parseCsvPreview } from "./csv";

describe("CSV Artifact preview", () => {
  it("parses commas, escaped quotes, and embedded newlines", () => {
    expect(parseCsvPreview('name,note\r\n"Ada","a, b"\n"Lin","say ""hi"""')).toEqual({
      rows: [
        ["name", "note"],
        ["Ada", "a, b"],
        ["Lin", 'say "hi"'],
      ],
      truncated: false,
    });
  });

  it("bounds rendered rows", () => {
    expect(parseCsvPreview("a\n1\n2\n3", 2)).toEqual({
      rows: [["a"], ["1"]],
      truncated: true,
    });
  });
});
