import { describe, expect, it } from "vitest";

import { consumeSseStream, type SseFrame } from "./sse";

function byteStream(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(chunk);
      }
      controller.close();
    },
  });
}

function chunkedStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return byteStream(chunks.map((chunk) => encoder.encode(chunk)));
}

describe("consumeSseStream", () => {
  it("parses frames split across UTF-8 and CRLF chunk boundaries", async () => {
    const frames: SseFrame[] = [];
    const payload =
      'id: evt-1\r\nevent: assistant_delta\r\ndata: {"content":"你好"}\r\n\r\n' +
      'id: evt-2\nevent: run_end\ndata: {"status":"success"}\n\n';
    const encoder = new TextEncoder();
    const bytes = encoder.encode(payload);
    const chineseStart = encoder.encode(
      payload.slice(0, payload.indexOf("你")),
    ).length;
    const crlfBoundary = encoder.encode(
      payload.slice(0, payload.indexOf("\r\n\r\n") + 1),
    ).length;
    const chunks = [
      bytes.slice(0, chineseStart + 1),
      bytes.slice(chineseStart + 1, crlfBoundary),
      bytes.slice(crlfBoundary),
    ];

    await consumeSseStream(byteStream(chunks), (frame) => frames.push(frame));

    expect(frames).toEqual([
      {
        id: "evt-1",
        event: "assistant_delta",
        data: { content: "你好" },
      },
      {
        id: "evt-2",
        event: "run_end",
        data: { status: "success" },
      },
    ]);
  });

  it("joins multiline data and ignores comment-only frames", async () => {
    const frames: SseFrame[] = [];
    await consumeSseStream(
      chunkedStream([
        ": keepalive\n\n",
        "id: one\nevent: custom\ndata: {\"value\":\ndata: 1}\n\n",
      ]),
      (frame) => frames.push(frame),
    );

    expect(frames).toEqual([
      { id: "one", event: "custom", data: { value: 1 } },
    ]);
  });

  it("rejects malformed JSON instead of corrupting live state", async () => {
    await expect(
      consumeSseStream(
        chunkedStream(["event: error\ndata: {broken}\n\n"]),
        () => undefined,
      ),
    ).rejects.toThrow("流式响应包含无效 JSON");
  });
});
