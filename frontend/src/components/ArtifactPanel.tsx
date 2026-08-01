import {
  CodeOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import { Button, Empty, Popconfirm, Tooltip } from "antd";
import { lazy, Suspense, useState } from "react";

import { artifactDownloadUrl } from "../api/artifacts";
import type { FileMetadata } from "../types/api";
import { formatSize } from "../utils/files";
import { FileShelf } from "./FileShelf";

const ArtifactPreview = lazy(() => import("./ArtifactPreview"));

interface ArtifactPanelProps {
  threadId: string | null;
  files: FileMetadata[];
  artifacts: FileMetadata[];
  disabled: boolean;
  uploading: boolean;
  onUpload: (file: File) => Promise<void>;
  onDelete: (fileId: string) => Promise<void>;
}

export function ArtifactPanel({
  threadId,
  files,
  artifacts,
  disabled,
  uploading,
  onUpload,
  onDelete,
}: ArtifactPanelProps) {
  const [previewing, setPreviewing] = useState<FileMetadata | null>(null);

  return (
    <aside className="artifact-panel" aria-label="文件与生成成果">
      <header className="artifact-panel-header">
        <div>
          <span className="section-label">FILES / ARTIFACTS</span>
          <h1>交付台</h1>
        </div>
        <span className="artifact-total">{files.length + artifacts.length}</span>
      </header>

      <div className="artifact-panel-scroll">
        <FileShelf
          files={files}
          disabled={disabled}
          uploading={uploading}
          onUpload={onUpload}
          onDelete={onDelete}
        />

        <section className="resource-section artifacts" aria-labelledby="artifacts-title">
          <div className="resource-heading">
            <div>
              <span className="resource-index">
                OUTPUT / {String(artifacts.length).padStart(2, "0")}
              </span>
              <h2 id="artifacts-title">生成成果</h2>
            </div>
          </div>

          <div className="resource-list">
            {artifacts.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="Agent 生成的文件会立即出现在这里"
              />
            ) : (
              artifacts.map((artifact) => (
                <article className="resource-card artifact" key={artifact.id}>
                  <span className="resource-icon" aria-hidden="true">
                    <CodeOutlined />
                  </span>
                  <div className="resource-copy">
                    <Tooltip title={artifact.original_name}>
                      <strong>{artifact.original_name}</strong>
                    </Tooltip>
                    <small>
                      {formatSize(artifact.size_bytes)} ·{" "}
                      {artifact.extension?.slice(1).toUpperCase()}
                    </small>
                    {artifact.description !== null && (
                      <p>{artifact.description}</p>
                    )}
                  </div>
                  <div className="artifact-actions">
                    <Tooltip title="预览">
                      <Button
                        type="text"
                        size="small"
                        icon={<EyeOutlined />}
                        disabled={threadId === null}
                        aria-label={`预览 ${artifact.original_name}`}
                        onClick={() => setPreviewing(artifact)}
                      />
                    </Tooltip>
                    <Tooltip title="下载">
                      <Button
                        type="text"
                        size="small"
                        icon={<DownloadOutlined />}
                        disabled={threadId === null}
                        aria-label={`下载 ${artifact.original_name}`}
                        href={
                          threadId === null
                            ? undefined
                            : artifactDownloadUrl(threadId, artifact.id)
                        }
                      />
                    </Tooltip>
                    <Popconfirm
                      title="删除这个成果？"
                      okText="删除"
                      cancelText="取消"
                      disabled={disabled}
                      onConfirm={() => void onDelete(artifact.id)}
                    >
                      <Tooltip title="删除">
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          disabled={disabled}
                          aria-label={`删除 ${artifact.original_name}`}
                        />
                      </Tooltip>
                    </Popconfirm>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </div>

      {threadId !== null && previewing !== null && (
        <Suspense fallback={null}>
          <ArtifactPreview
            key={previewing.id}
            threadId={threadId}
            artifact={previewing}
            onClose={() => setPreviewing(null)}
          />
        </Suspense>
      )}
    </aside>
  );
}
