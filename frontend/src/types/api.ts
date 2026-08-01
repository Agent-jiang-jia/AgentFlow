export interface ThreadSummary {
  id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  thread_id: string;
  run_id: string | null;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  message_type: "text" | "tool_call" | "tool_result" | "error";
  metadata: Record<string, unknown>;
  sequence_number: number;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export type SseEventName =
  | "run_start"
  | "assistant_start"
  | "assistant_delta"
  | "tool_start"
  | "tool_result"
  | "artifact_created"
  | "assistant_end"
  | "run_end"
  | "error";

export interface SseEvent {
  event_id: string;
  event: SseEventName;
  thread_id: string;
  run_id: string;
  timestamp: string;
  data: Record<string, unknown>;
}
