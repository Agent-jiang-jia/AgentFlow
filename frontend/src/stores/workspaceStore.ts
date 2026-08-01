import { create } from "zustand";

import { streamChat } from "../api/chat";
import { fetchArtifacts } from "../api/artifacts";
import {
  deleteFile as deleteFileRequest,
  fetchFiles,
  uploadFile as uploadFileRequest,
} from "../api/files";
import {
  createThread as createThreadRequest,
  deleteThread as deleteThreadRequest,
  fetchMessages,
  fetchThreads,
} from "../api/threads";
import type {
  FileMetadata,
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
  files: FileMetadata[];
  artifacts: FileMetadata[];
  loading: boolean;
  streaming: boolean;
  uploading: boolean;
  error: string | null;
  initialize: () => Promise<void>;
  createThread: () => Promise<void>;
  selectThread: (threadId: string) => Promise<void>;
  deleteThread: (threadId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
  deleteFile: (fileId: string) => Promise<void>;
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
  files: [],
  artifacts: [],
  loading: true,
  streaming: false,
  uploading: false,
  error: null,

  initialize: async () => {
    set({ loading: true, error: null });
    try {
      const threads = await reloadThreads();
      const currentThreadId = threads[0]?.id ?? null;
      const [messages, files, artifacts] =
        currentThreadId === null
          ? [[], [], []]
          : await Promise.all([
              fetchMessages(currentThreadId).then((page) => page.items),
              fetchFiles(currentThreadId).then((page) => page.items),
              fetchArtifacts(currentThreadId).then((page) => page.items),
            ]);
      set({
        threads,
        currentThreadId,
        messages,
        files,
        artifacts,
        toolActivities: [],
        loading: false,
      });
    } catch (error: unknown) {
      set({ error: errorMessage(error), loading: false });
    }
  },

  createThread: async () => {
    if (get().streaming || get().uploading) {
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
        files: [],
        artifacts: [],
        streamingMessage: null,
        toolActivities: [],
      });
    } catch (error: unknown) {
      set({ error: errorMessage(error) });
    }
  },

  selectThread: async (threadId: string) => {
    if (get().streaming || get().uploading || get().currentThreadId === threadId) {
      return;
    }
    set({
      currentThreadId: threadId,
      messages: [],
      files: [],
      artifacts: [],
      streamingMessage: null,
      toolActivities: [],
      loading: true,
      error: null,
    });
    try {
      const [messages, files, artifacts] = await Promise.all([
        fetchMessages(threadId).then((page) => page.items),
        fetchFiles(threadId).then((page) => page.items),
        fetchArtifacts(threadId).then((page) => page.items),
      ]);
      if (get().currentThreadId === threadId) {
        set({ messages, files, artifacts, loading: false });
      }
    } catch (error: unknown) {
      if (get().currentThreadId === threadId) {
        set({ error: errorMessage(error), loading: false });
      }
    }
  },

  deleteThread: async (threadId: string) => {
    if (get().streaming || get().uploading) {
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
      const [messages, files, artifacts] =
        currentThreadId === null
          ? [[], [], []]
          : await Promise.all([
              fetchMessages(currentThreadId).then((page) => page.items),
              fetchFiles(currentThreadId).then((page) => page.items),
              fetchArtifacts(currentThreadId).then((page) => page.items),
            ]);
      set({
        threads,
        currentThreadId,
        messages,
        files,
        artifacts,
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
      } else if (event.event === "artifact_created") {
        void fetchArtifacts(threadId)
          .then((page) => {
            if (get().currentThreadId === threadId) {
              set({ artifacts: page.items });
            }
          })
          .catch(() => {
            // The final authoritative reload reports a persistent failure.
          });
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
        const [threads, history, filePage, artifactPage] = await Promise.all([
          reloadThreads(),
          fetchMessages(threadId),
          fetchFiles(threadId),
          fetchArtifacts(threadId),
        ]);
        if (get().currentThreadId === threadId) {
          set({
            threads,
            messages: history.items,
            files: filePage.items,
            artifacts: artifactPage.items,
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

  uploadFile: async (file: File) => {
    const threadId = get().currentThreadId;
    if (threadId === null || get().streaming || get().uploading) {
      return;
    }
    set({ uploading: true, error: null });
    try {
      await uploadFileRequest(threadId, file);
      const [files, artifacts, threads] = await Promise.all([
        fetchFiles(threadId),
        fetchArtifacts(threadId),
        reloadThreads(),
      ]);
      if (get().currentThreadId === threadId) {
        set({ files: files.items, artifacts: artifacts.items, threads, uploading: false });
      } else {
        set({ threads, uploading: false });
      }
    } catch (error: unknown) {
      let files = get().files;
      try {
        files = (await fetchFiles(threadId)).items;
      } catch {
        // Preserve the original upload error when refresh also fails.
      }
      set({ files, error: errorMessage(error), uploading: false });
    }
  },

  deleteFile: async (fileId: string) => {
    const threadId = get().currentThreadId;
    if (threadId === null || get().streaming || get().uploading) {
      return;
    }
    set({ uploading: true, error: null });
    try {
      await deleteFileRequest(threadId, fileId);
      const [files, artifacts, threads] = await Promise.all([
        fetchFiles(threadId),
        fetchArtifacts(threadId),
        reloadThreads(),
      ]);
      if (get().currentThreadId === threadId) {
        set({ files: files.items, artifacts: artifacts.items, threads, uploading: false });
      } else {
        set({ threads, uploading: false });
      }
    } catch (error: unknown) {
      set({ error: errorMessage(error), uploading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
