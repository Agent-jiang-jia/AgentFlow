import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Message, ThreadSummary } from "../types/api";

const api = vi.hoisted(() => ({
  streamChat: vi.fn(),
  fetchArtifacts: vi.fn(),
  deleteFile: vi.fn(),
  fetchFiles: vi.fn(),
  uploadFile: vi.fn(),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
  fetchMessages: vi.fn(),
  fetchThreads: vi.fn(),
}));

vi.mock("../api/chat", () => ({ streamChat: api.streamChat }));
vi.mock("../api/artifacts", () => ({ fetchArtifacts: api.fetchArtifacts }));
vi.mock("../api/files", () => ({
  deleteFile: api.deleteFile,
  fetchFiles: api.fetchFiles,
  uploadFile: api.uploadFile,
}));
vi.mock("../api/threads", () => ({
  createThread: api.createThread,
  deleteThread: api.deleteThread,
  fetchMessages: api.fetchMessages,
  fetchThreads: api.fetchThreads,
}));

import { useWorkspaceStore } from "./workspaceStore";

const thread: ThreadSummary = {
  id: "thread-1",
  title: "Recovery",
  status: "active",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

const authoritativeMessage: Message = {
  id: "message-1",
  thread_id: thread.id,
  run_id: "run-1",
  role: "user",
  content: "persisted by the backend",
  message_type: "text",
  metadata: {},
  sequence_number: 1,
  created_at: "2026-08-01T00:00:01Z",
};

describe("workspace stream recovery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchThreads.mockResolvedValue({
      items: [thread],
      page: 1,
      page_size: 20,
      total: 1,
    });
    api.fetchMessages.mockResolvedValue({
      items: [authoritativeMessage],
      page: 1,
      page_size: 20,
      total: 1,
    });
    api.fetchFiles.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
    api.fetchArtifacts.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 100,
      total: 0,
    });
    useWorkspaceStore.setState({
      threads: [thread],
      currentThreadId: thread.id,
      messages: [],
      streamingMessage: null,
      toolActivities: [],
      files: [],
      artifacts: [],
      loading: false,
      streaming: false,
      uploading: false,
      error: null,
    });
  });

  it("reloads backend authority after a broken SSE stream", async () => {
    api.streamChat.mockRejectedValue(new Error("流式事件结构无效"));

    await useWorkspaceStore.getState().sendMessage("client message");

    const state = useWorkspaceStore.getState();
    expect(state.streaming).toBe(false);
    expect(state.streamingMessage).toBeNull();
    expect(state.messages).toEqual([authoritativeMessage]);
    expect(state.error).toBe("流式事件结构无效");
    expect(api.fetchMessages).toHaveBeenCalledWith(thread.id);
    expect(api.fetchFiles).toHaveBeenCalledWith(thread.id);
    expect(api.fetchArtifacts).toHaveBeenCalledWith(thread.id);
  });
});
