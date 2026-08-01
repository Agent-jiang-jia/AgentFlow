import { describe, expect, it } from "vitest";

import type { SseEvent } from "../types/api";
import { applyToolResult, applyToolStart } from "./toolActivity";

function event(
  name: SseEvent["event"],
  data: Record<string, unknown>,
): SseEvent {
  return {
    event_id: crypto.randomUUID(),
    event: name,
    thread_id: "thread-id",
    run_id: "run-id",
    timestamp: "2026-08-01T08:00:00Z",
    data,
  };
}

describe("tool activity projection", () => {
  it("projects safe start and terminal summaries in execution order", () => {
    const started = applyToolStart(
      [],
      event("tool_start", {
        tool_call_id: "call-1",
        tool_name: "get_current_time",
        display_name: "正在查询当前时间",
        arguments: { timezone: "UTC" },
      }),
    );
    const finished = applyToolResult(
      started,
      event("tool_result", {
        tool_call_id: "call-1",
        tool_name: "get_current_time",
        status: "success",
        summary: "已获取 UTC 当前时间",
      }),
    );

    expect(finished).toEqual([
      {
        toolCallId: "call-1",
        runId: "run-id",
        toolName: "get_current_time",
        displayName: "正在查询当前时间",
        status: "success",
        summary: "已获取 UTC 当前时间",
      },
    ]);
  });

  it("ignores malformed or unknown status events", () => {
    const started = applyToolStart(
      [],
      event("tool_start", { tool_call_id: "missing-fields" }),
    );
    const finished = applyToolResult(
      [],
      event("tool_result", {
        tool_call_id: "call-1",
        status: "unexpected",
      }),
    );
    expect(started).toEqual([]);
    expect(finished).toEqual([]);
  });
});
