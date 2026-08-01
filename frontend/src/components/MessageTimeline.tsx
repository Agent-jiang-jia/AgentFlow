import { RobotOutlined, UserOutlined } from "@ant-design/icons";
import { Avatar, Empty, Spin, Typography } from "antd";
import { useEffect, useMemo, useRef } from "react";
import { Fragment } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import type { Message, ToolActivity } from "../types/api";
import { parseSources } from "../utils/sources";
import { SourceReferences } from "./SourceReferences";
import { ToolStatusLedger } from "./ToolStatusLedger";

interface MessageTimelineProps {
  messages: Message[];
  streamingMessage: Message | null;
  toolActivities: ToolActivity[];
  loading: boolean;
  streaming: boolean;
  hasThread: boolean;
  onCreateThread: () => void;
}

export function MessageTimeline({
  messages,
  streamingMessage,
  toolActivities,
  loading,
  streaming,
  hasThread,
  onCreateThread,
}: MessageTimelineProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const visibleMessages = useMemo(
    () =>
      streamingMessage === null ? messages : [...messages, streamingMessage],
    [messages, streamingMessage],
  );

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [toolActivities, visibleMessages]);

  if (loading) {
    return (
      <div className="timeline-state">
        <Spin />
        <Typography.Text type="secondary">正在恢复会话…</Typography.Text>
      </div>
    );
  }

  if (!hasThread) {
    return (
      <div className="timeline-state empty-conversation">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="创建一个会话，开始记录你的问题与回答"
        >
          <button type="button" className="text-action" onClick={onCreateThread}>
            创建第一个会话 →
          </button>
        </Empty>
      </div>
    );
  }

  if (visibleMessages.length === 0) {
    return (
      <div className="opening-note">
        <span className="opening-index">READY / 01</span>
        <Typography.Title level={2}>从一个清晰的问题开始。</Typography.Title>
        <Typography.Paragraph>
          这次会话会保存在本机。你可以连续追问，刷新页面后继续。
        </Typography.Paragraph>
      </div>
    );
  }

  return (
    <div className="message-timeline">
      {visibleMessages.map((message) => {
        const isUser = message.role === "user";
        const isLive = streamingMessage?.id === message.id;
        const sources = isUser ? [] : parseSources(message.metadata);
        const runActivities =
          message.role === "assistant" && message.run_id !== null
            ? toolActivities.filter(
                (activity) => activity.runId === message.run_id,
              )
            : [];
        return (
          <Fragment key={message.id}>
            {runActivities.length > 0 && (
              <ToolStatusLedger activities={runActivities} />
            )}
            <article
              className={`message-entry ${isUser ? "user" : "assistant"}`}
            >
              <div className="message-rail">
                <Avatar
                  size={30}
                  icon={isUser ? <UserOutlined /> : <RobotOutlined />}
                />
                <span className="rail-line" />
              </div>
              <div className="message-body">
                <div className="message-meta">
                  <span>{isUser ? "你" : "AgentFlow"}</span>
                  {isLive && (
                    <span className="live-label">
                      <i />
                      正在生成
                    </span>
                  )}
                </div>
                {isUser ? (
                  <p className="user-copy">{message.content}</p>
                ) : (
                  <div className="markdown-body">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeHighlight]}
                    >
                      {message.content}
                    </ReactMarkdown>
                    {isLive && streaming && message.content.length === 0 && (
                      <span
                        className="typing-cursor"
                        aria-label="等待模型响应"
                      />
                    )}
                  </div>
                )}
                {!isUser && <SourceReferences sources={sources} />}
              </div>
            </article>
          </Fragment>
        );
      })}
      <ToolStatusLedger
        activities={toolActivities.filter(
          (activity) =>
            !visibleMessages.some(
              (message) =>
                message.role === "assistant" &&
                message.run_id === activity.runId,
            ),
        )}
      />
      <div ref={endRef} />
    </div>
  );
}
