import {
  ApiOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { Alert, Button, Card, Flex, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";

import { fetchHealth, type HealthResponse } from "./api/health";

type ConnectionState =
  | { kind: "checking" }
  | { kind: "healthy"; health: HealthResponse }
  | { kind: "error"; message: string };

function toErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "无法连接到后端服务";
}

export default function App() {
  const [connection, setConnection] = useState<ConnectionState>({
    kind: "checking",
  });

  useEffect(() => {
    const controller = new AbortController();
    void fetchHealth(controller.signal).then(
      (health) => setConnection({ kind: "healthy", health }),
      (error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setConnection({ kind: "error", message: toErrorMessage(error) });
      },
    );
    return () => controller.abort();
  }, []);

  const retryConnection = async () => {
    setConnection({ kind: "checking" });
    try {
      const health = await fetchHealth();
      setConnection({ kind: "healthy", health });
    } catch (error: unknown) {
      setConnection({ kind: "error", message: toErrorMessage(error) });
    }
  };

  return (
    <main className="app-shell">
      <Card className="status-card" bordered={false}>
        <Flex vertical gap={24}>
          <Space direction="vertical" size={4}>
            <Typography.Text className="eyebrow">
              MINI DEERFLOW V1
            </Typography.Text>
            <Typography.Title level={1}>AgentFlow</Typography.Title>
            <Typography.Paragraph type="secondary">
              轻量级单 Agent 工作台 · Phase 1 基础设施
            </Typography.Paragraph>
          </Space>

          {connection.kind === "checking" && (
            <Flex align="center" gap={12} className="connection-panel">
              <Spin size="small" />
              <Typography.Text>正在检查后端连接…</Typography.Text>
            </Flex>
          )}

          {connection.kind === "healthy" && (
            <Flex vertical gap={12} className="connection-panel healthy">
              <Space>
                <CheckCircleOutlined className="success-icon" />
                <Typography.Text strong>后端连接正常</Typography.Text>
                <Tag color="success">SQLite {connection.health.database}</Tag>
              </Space>
              <Typography.Text type="secondary">
                {connection.health.service} · v{connection.health.version}
              </Typography.Text>
            </Flex>
          )}

          {connection.kind === "error" && (
            <Alert
              type="error"
              showIcon
              message="后端连接异常"
              description={connection.message}
              action={
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => void retryConnection()}
                >
                  重新检查
                </Button>
              }
            />
          )}

          <Flex justify="space-between" align="center" wrap>
            <Space>
              <ApiOutlined />
              <Typography.Text type="secondary">
                当前仅提供健康检查；对话工作台将在后续 Phase 实现。
              </Typography.Text>
            </Space>
            <Tag bordered={false}>Phase 1</Tag>
          </Flex>
        </Flex>
      </Card>
    </main>
  );
}
