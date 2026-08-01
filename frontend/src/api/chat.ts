import type { SseEvent, SseEventName } from "../types/api";
import { consumeSseStream } from "../utils/sse";
import { API_BASE_URL, isRecord, responseError } from "./client";

const EVENT_NAMES = new Set<SseEventName>([
  "run_start",
  "assistant_start",
  "assistant_delta",
  "tool_start",
  "tool_result",
  "artifact_created",
  "assistant_end",
  "run_end",
  "error",
]);

function isSseEvent(value: unknown): value is SseEvent {
  if (!isRecord(value) || !EVENT_NAMES.has(value.event as SseEventName)) {
    return false;
  }
  return (
    typeof value.event_id === "string" &&
    typeof value.event === "string" &&
    typeof value.thread_id === "string" &&
    typeof value.run_id === "string" &&
    typeof value.timestamp === "string" &&
    isRecord(value.data)
  );
}

export async function streamChat({
  threadId,
  message,
  signal,
  onEvent,
}: {
  threadId: string;
  message: string;
  signal?: AbortSignal;
  onEvent: (event: SseEvent) => void;
}): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/threads/${encodeURIComponent(threadId)}/chat/stream`,
    {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message, file_ids: [] }),
      signal,
    },
  );
  if (!response.ok) {
    throw await responseError(response);
  }
  if (response.body === null) {
    throw new Error("浏览器未提供流式响应");
  }

  const processedEventIds = new Set<string>();
  await consumeSseStream(response.body, (frame) => {
    if (!isSseEvent(frame.data)) {
      if (EVENT_NAMES.has(frame.event as SseEventName)) {
        throw new Error("流式事件结构无效");
      }
      return;
    }
    if (
      frame.id !== frame.data.event_id ||
      frame.event !== frame.data.event ||
      processedEventIds.has(frame.data.event_id)
    ) {
      return;
    }
    processedEventIds.add(frame.data.event_id);
    onEvent(frame.data);
  });
}
