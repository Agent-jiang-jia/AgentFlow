import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from "@ant-design/icons";

import type {
  ToolActivity,
  ToolActivityStatus,
} from "../types/api";

interface ToolStatusLedgerProps {
  activities: ToolActivity[];
}

const STATUS_LABELS: Record<ToolActivityStatus, string> = {
  running: "执行中",
  success: "已完成",
  failed: "执行失败",
  timeout: "已超时",
  rejected: "已阻止",
};

function StatusIcon({ status }: { status: ToolActivityStatus }) {
  if (status === "running") {
    return <LoadingOutlined spin />;
  }
  if (status === "success") {
    return <CheckCircleOutlined />;
  }
  return <CloseCircleOutlined />;
}

export function ToolStatusLedger({
  activities,
}: ToolStatusLedgerProps) {
  if (activities.length === 0) {
    return null;
  }

  return (
    <section className="tool-ledger" aria-label="工具执行状态">
      <div className="tool-ledger-heading">
        <span>TOOL TRACE</span>
        <span>{activities.length.toString().padStart(2, "0")}</span>
      </div>
      {activities.map((activity, index) => (
        <div
          className={`tool-step ${activity.status}`}
          key={activity.toolCallId}
        >
          <span className="tool-step-index">
            {(index + 1).toString().padStart(2, "0")}
          </span>
          <span className="tool-step-icon" aria-hidden="true">
            <StatusIcon status={activity.status} />
          </span>
          <span className="tool-step-copy">
            <strong>{activity.displayName}</strong>
            <small>
              {activity.summary ??
                (activity.status === "running"
                  ? "工具正在顺序执行"
                  : STATUS_LABELS[activity.status])}
            </small>
          </span>
          <span className="tool-step-status">
            {STATUS_LABELS[activity.status]}
          </span>
        </div>
      ))}
    </section>
  );
}
