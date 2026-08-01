import { create } from "zustand";

import { streamChat } from "../api/chat";
import {
  createThread as createThreadRequest,
  deleteThread as deleteThreadRequest,
  fetchMessages,
  fetchThreads,
} from "../api/threads";
import type {
  Message,
  SseEvent,
  ThreadSummary,
  ToolActivity,
} from "../types/api";
import {
  applyToolResult,
  applyToolStart,
} from "../utils/toolActivity";

interface WorkspaceState {
  threads: ThreadSummary[];
  currentThreadId: string | null;
  messages: Message[];
  streamingMessage: Message | null;
  toolActivities: ToolActivity[];
  loading: boolean;
  streaming: boolean;
  error: string | null;
  initialize: () => Promise<void>;
  createThread: () => Promise<void>;
  selectThread: (threadId: string) => Promise<void>;
  deleteThread: (threadId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  clearError: () => void;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "请求失败，请检查后端连接";
}

function localUserMessage(threadId: string, content: string): Message {
  return {
    id: `local-${crypto.randomUUID()}`,
    thread_id: threadId,
    run_id: null,
    role: "user",
    content,
    message_type: "text",
    metadata: {},
    sequence_number: Number.MAX_SAFE_INTEGER,
    created_at: new Date().toISOString(),
  };
}

function localAssistantMessage(
  threadId: string,
  runId: string,
  messageId: string,
  content = "",
): Message {
  return {
    id: messageId,
    thread_id: threadId,
    run_id: runId,
    role: "assistant",
    content,
    message_type: "text",
    metadata: {},
    sequence_number: Number.MAX_SAFE_INTEGER,
    created_at: new Date().toISOString(),
  };
}

async function reloadThreads(): Promise<ThreadSummary[]> {
  return (await fetchThreads()).items;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  threads: [],
  currentThreadId: null,
  messages: [],
  streamingMessage: null,
  toolActivities: [],
  loading: true,
  streaming: false,
  error: null,

  initialize: async () => {
    set({ loading: true, error: null });
    try {
      const threads = await reloadThreads();
      const currentThreadId = threads[0]?.id ?? null;
      const messages =
        currentThreadId === null
          ? []
          : (await fetchMessages(currentThreadId)).items;
      set({
        threads,
        currentThreadId,
        messages,
        toolActivities: [],
        loading: false,
      });
    } catch (error: unknown) {
      set({ error: errorMessage(error), loading: false });
    }
  },

  createThread: async () => {
    if (get().streaming) {
      return;
    }
    set({ error: null });
    try {
      const thread = await createThreadRequest();
      const threads = await reloadThreads();
      set({
        threads,
        currentThreadId: thread.id,
        messages: [],
        streamingMessage: null,
        toolActivities: [],
      });
    } catch (error: unknown) {
      set({ error: errorMessage(error) });
    }
  },

  selectThread: async (threadId: string) => {
    if (get().streaming || get().currentThreadId === threadId) {
      return;
    }
    set({
      currentThreadId: threadId,
      messages: [],
      streamingMessage: null,
      toolActivities: [],
      loading: true,
      error: null,
    });
    try {
      const messages = (await fetchMessages(threadId)).items;
      if (get().currentThreadId === threadId) {
        set({ messages, loading: false });
      }
    } catch (error: unknown) {
      if (get().currentThreadId === threadId) {
        set({ error: errorMessage(error), loading: false });
      }
    }
  },

  deleteThread: async (threadId: string) => {
    if (get().streaming) {
      return;
    }
    set({ error: null });
    try {
      await deleteThreadRequest(threadId);
      const threads = await reloadThreads();
      const currentThreadId =
        get().currentThreadId === threadId
          ? (threads[0]?.id ?? null)
          : get().currentThreadId;
      const messages =
        currentThreadId === null
          ? []
          : (await fetchMessages(currentThreadId)).items;
      set({
        threads,
        currentThreadId,
        messages,
        streamingMessage: null,
        toolActivities: [],
      });
    } catch (error: unknown) {
      set({ error: errorMessage(error) });
    }
  },

  sendMessage: async (rawContent: string) => {
    const content = rawContent.trim();
    const threadId = get().currentThreadId;
    if (!content || threadId === null || get().streaming) {
      return;
    }

    set((state) => ({
      messages: [...state.messages, localUserMessage(threadId, content)],
      streamingMessage: null,
      toolActivities: [],
      streaming: true,
      error: null,
    }));

    const handleEvent = (event: SseEvent) => {
      if (get().currentThreadId !== threadId) {
        return;
      }
      if (event.event === "assistant_start") {
        const messageId = event.data.message_id;
        if (typeof messageId === "string") {
          set({
            streamingMessage: localAssistantMessage(
              threadId,
              event.run_id,
              messageId,
            ),
          });
        }
      } else if (event.event === "assistant_delta") {
        const delta = event.data.content;
        if (typeof delta === "string") {
          set((state) => ({
            streamingMessage:
              state.streamingMessage === null
                ? state.streamingMessage
                : {
                    ...state.streamingMessage,
                    content: state.streamingMessage.content + delta,
                  },
          }));
        }
      } else if (event.event === "assistant_end") {
        const completeContent = event.data.content;
        const sources = event.data.sources;
        if (typeof completeContent === "string") {
          set((state) => ({
            streamingMessage:
              state.streamingMessage === null
                ? state.streamingMessage
                : {
                    ...state.streamingMessage,
                    content: completeContent,
                    metadata: Array.isArray(sources)
                      ? { sources }
                      : state.streamingMessage.metadata,
                  },
          }));
        }
      } else if (event.event === "tool_start") {
        set((state) => ({
          toolActivities: applyToolStart(state.toolActivities, event),
        }));
      } else if (event.event === "tool_result") {
        set((state) => ({
          toolActivities: applyToolResult(state.toolActivities, event),
        }));
      } else if (event.event === "error") {
        const message = event.data.message;
        set({ error: typeof message === "string" ? message : "对话执行失败" });
      }
    };

    try {
      await streamChat({ threadId, message: content, onEvent: handleEvent });
    } catch (error: unknown) {
      set({ error: errorMessage(error) });
    } finally {
      try {
        const [threads, history] = await Promise.all([
          reloadThreads(),
          fetchMessages(threadId),
        ]);
        if (get().currentThreadId === threadId) {
          set({
            threads,
            messages: history.items,
            streamingMessage: null,
            streaming: false,
          });
        }
      } catch (error: unknown) {
        set({
          error: errorMessage(error),
          streamingMessage: null,
          streaming: false,
        });
      }
    }
  },

  clearError: () => set({ error: null }),
}));
