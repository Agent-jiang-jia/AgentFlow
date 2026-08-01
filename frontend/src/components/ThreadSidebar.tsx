import {
  DeleteOutlined,
  MessageOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { Button, Popconfirm, Tooltip, Typography } from "antd";

import type { ThreadSummary } from "../types/api";

function updatedLabel(value: string): string {
  const date = new Date(value);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return new Intl.DateTimeFormat("zh-CN", {
    month: sameDay ? undefined : "numeric",
    day: sameDay ? undefined : "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

interface ThreadSidebarProps {
  threads: ThreadSummary[];
  currentThreadId: string | null;
  disabled: boolean;
  onCreate: () => void;
  onSelect: (threadId: string) => void;
  onDelete: (threadId: string) => void;
}

export function ThreadSidebar({
  threads,
  currentThreadId,
  disabled,
  onCreate,
  onSelect,
  onDelete,
}: ThreadSidebarProps) {
  return (
    <aside className="thread-sidebar">
      <header className="brand-lockup">
        <div className="brand-mark" aria-hidden="true">
          AF
        </div>
        <div>
          <Typography.Title level={3}>AgentFlow</Typography.Title>
          <Typography.Text>LOCAL WORKBENCH / 02</Typography.Text>
        </div>
      </header>

      <Button
        className="new-thread-button"
        type="primary"
        icon={<PlusOutlined />}
        block
        disabled={disabled}
        onClick={onCreate}
      >
        新建会话
      </Button>

      <div className="thread-index-heading">
        <span>会话索引</span>
        <span>{String(threads.length).padStart(2, "0")}</span>
      </div>

      <nav className="thread-list" aria-label="历史会话">
        {threads.map((thread) => {
          const active = thread.id === currentThreadId;
          return (
            <div
              className={`thread-row${active ? " active" : ""}`}
              key={thread.id}
            >
              <button
                type="button"
                className="thread-select"
                disabled={disabled}
                onClick={() => onSelect(thread.id)}
              >
                <MessageOutlined />
                <span className="thread-copy">
                  <span className="thread-title">{thread.title}</span>
                  <span className="thread-time">
                    {updatedLabel(thread.updated_at)}
                  </span>
                </span>
              </button>
              <Popconfirm
                title="删除这个会话？"
                description="历史消息和会话目录将一并删除。"
                okText="删除"
                cancelText="取消"
                disabled={disabled}
                onConfirm={() => onDelete(thread.id)}
              >
                <Tooltip title="删除会话">
                  <Button
                    className="thread-delete"
                    type="text"
                    size="small"
                    danger
                    disabled={disabled}
                    aria-label={`删除 ${thread.title}`}
                    icon={<DeleteOutlined />}
                  />
                </Tooltip>
              </Popconfirm>
            </div>
          );
        })}
        {threads.length === 0 && (
          <div className="thread-empty">
            <span className="empty-rule" />
            还没有会话
          </div>
        )}
      </nav>

      <footer className="sidebar-footer">
        <span className="connection-dot" />
        本地数据已连接
      </footer>
    </aside>
  );
}
