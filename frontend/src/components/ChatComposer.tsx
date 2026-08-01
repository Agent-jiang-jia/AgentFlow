import { ArrowUpOutlined } from "@ant-design/icons";
import { Button, Input, Typography } from "antd";
import { type KeyboardEvent, useState } from "react";

interface ChatComposerProps {
  disabled: boolean;
  streaming: boolean;
  onSend: (content: string) => Promise<void>;
}

export function ChatComposer({
  disabled,
  streaming,
  onSend,
}: ChatComposerProps) {
  const [value, setValue] = useState("");

  const send = async () => {
    const content = value.trim();
    if (!content || disabled) {
      return;
    }
    setValue("");
    await onSend(content);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  };

  return (
    <div className="composer-wrap">
      <div className={`composer${streaming ? " running" : ""}`}>
        <Input.TextArea
          value={value}
          disabled={disabled}
          autoSize={{ minRows: 1, maxRows: 6 }}
          maxLength={20_000}
          placeholder={disabled ? "请先创建会话" : "输入问题，Enter 发送…"}
          aria-label="聊天消息"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <Button
          type="primary"
          shape="circle"
          size="large"
          icon={<ArrowUpOutlined />}
          disabled={disabled || value.trim().length === 0}
          loading={streaming}
          aria-label="发送消息"
          onClick={() => void send()}
        />
      </div>
      <Typography.Text className="composer-hint">
        Enter 发送 · Shift + Enter 换行 · 对话保存在本机
      </Typography.Text>
    </div>
  );
}
