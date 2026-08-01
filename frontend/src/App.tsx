import { Alert, Tag, Typography } from "antd";
import { useEffect } from "react";

import { ChatComposer } from "./components/ChatComposer";
import { MessageTimeline } from "./components/MessageTimeline";
import { ThreadSidebar } from "./components/ThreadSidebar";
import { useWorkspaceStore } from "./stores/workspaceStore";

export default function App() {
  const threads = useWorkspaceStore((state) => state.threads);
  const currentThreadId = useWorkspaceStore(
    (state) => state.currentThreadId,
  );
  const messages = useWorkspaceStore((state) => state.messages);
  const streamingMessage = useWorkspaceStore(
    (state) => state.streamingMessage,
  );
  const toolActivities = useWorkspaceStore(
    (state) => state.toolActivities,
  );
  const loading = useWorkspaceStore((state) => state.loading);
  const streaming = useWorkspaceStore((state) => state.streaming);
  const error = useWorkspaceStore((state) => state.error);
  const initialize = useWorkspaceStore((state) => state.initialize);
  const createThread = useWorkspaceStore((state) => state.createThread);
  const selectThread = useWorkspaceStore((state) => state.selectThread);
  const deleteThread = useWorkspaceStore((state) => state.deleteThread);
  const sendMessage = useWorkspaceStore((state) => state.sendMessage);
  const clearError = useWorkspaceStore((state) => state.clearError);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  const currentThread = threads.find(
    (thread) => thread.id === currentThreadId,
  );

  return (
    <main className="workspace-shell">
      <ThreadSidebar
        threads={threads}
        currentThreadId={currentThreadId}
        disabled={streaming}
        onCreate={() => void createThread()}
        onSelect={(threadId) => void selectThread(threadId)}
        onDelete={(threadId) => void deleteThread(threadId)}
      />

      <section className="chat-workspace">
        <header className="chat-header">
          <div>
            <Typography.Text className="section-label">
              CONVERSATION / LIVE
            </Typography.Text>
            <Typography.Title level={2}>
              {currentThread?.title ?? "选择一个会话"}
            </Typography.Title>
          </div>
          <Tag
            variant="filled"
            className={`run-status${streaming ? " active" : ""}`}
          >
            <span />
            {streaming ? "模型运行中" : "就绪"}
          </Tag>
        </header>

        {error !== null && (
          <Alert
            className="workspace-alert"
            type="error"
            showIcon
            closable
            title={error}
            onClose={clearError}
          />
        )}

        <div className="conversation-scroll">
          <MessageTimeline
            messages={messages}
            streamingMessage={streamingMessage}
            toolActivities={toolActivities}
            loading={loading}
            streaming={streaming}
            hasThread={currentThreadId !== null}
            onCreateThread={() => void createThread()}
          />
        </div>

        <ChatComposer
          disabled={currentThreadId === null || streaming || loading}
          streaming={streaming}
          onSend={sendMessage}
        />
      </section>
    </main>
  );
}
