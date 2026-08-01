import type {
  SseEvent,
  ToolActivity,
  ToolActivityStatus,
} from "../types/api";

function isTerminalStatus(value: unknown): value is ToolActivityStatus {
  return (
    value === "success" ||
    value === "failed" ||
    value === "timeout" ||
    value === "rejected"
  );
}

export function applyToolStart(
  activities: ToolActivity[],
  event: SseEvent,
): ToolActivity[] {
  const toolCallId = event.data.tool_call_id;
  const toolName = event.data.tool_name;
  const displayName = event.data.display_name;
  if (
    typeof toolCallId !== "string" ||
    typeof toolName !== "string" ||
    typeof displayName !== "string"
  ) {
    return activities;
  }
  return [
    ...activities.filter(
      (activity) => activity.toolCallId !== toolCallId,
    ),
    {
      toolCallId,
      runId: event.run_id,
      toolName,
      displayName,
      status: "running",
      summary: null,
    },
  ];
}

export function applyToolResult(
  activities: ToolActivity[],
  event: SseEvent,
): ToolActivity[] {
  const toolCallId = event.data.tool_call_id;
  const status = event.data.status;
  const summary = event.data.summary;
  if (
    typeof toolCallId !== "string" ||
    !isTerminalStatus(status)
  ) {
    return activities;
  }
  return activities.map((activity) =>
    activity.toolCallId === toolCallId
      ? {
          ...activity,
          status,
          summary:
            typeof summary === "string" ? summary : activity.summary,
        }
      : activity,
  );
}
