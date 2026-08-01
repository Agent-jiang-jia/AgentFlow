export interface SseFrame {
  id: string;
  event: string;
  data: unknown;
}

function parseFrame(rawFrame: string): SseFrame | null {
  let id = "";
  let event = "message";
  const dataLines: string[] = [];

  for (const line of rawFrame.split("\n")) {
    if (!line || line.startsWith(":")) {
      continue;
    }
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const rawValue = separator === -1 ? "" : line.slice(separator + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;
    if (field === "id") {
      id = value;
    } else if (field === "event") {
      event = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }

  if (dataLines.length === 0) {
    return null;
  }
  const serializedData = dataLines.join("\n");
  let data: unknown;
  try {
    data = JSON.parse(serializedData);
  } catch {
    throw new Error("流式响应包含无效 JSON");
  }
  return { id, event, data };
}

export async function consumeSseStream(
  stream: ReadableStream<Uint8Array>,
  onFrame: (frame: SseFrame) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer = (
        buffer + decoder.decode(value, { stream: !done })
      ).replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawFrame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const frame = parseFrame(rawFrame);
        if (frame !== null) {
          onFrame(frame);
        }
        boundary = buffer.indexOf("\n\n");
      }
      if (done) {
        break;
      }
    }
    if (buffer.trim()) {
      const frame = parseFrame(buffer);
      if (frame !== null) {
        onFrame(frame);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
