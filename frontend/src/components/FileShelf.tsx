import {
  DeleteOutlined,
  FileTextOutlined,
  LoadingOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { Button, Empty, Popconfirm, Tag, Tooltip } from "antd";
import { useRef } from "react";

import type { FileMetadata } from "../types/api";
import { formatSize } from "../utils/files";

const ACCEPTED_TYPES = ".pdf,.docx,.txt,.md,.csv";

interface FileShelfProps {
  files: FileMetadata[];
  disabled: boolean;
  uploading: boolean;
  onUpload: (file: File) => Promise<void>;
  onDelete: (fileId: string) => Promise<void>;
}

function statusLabel(status: string | null): string {
  const labels: Record<string, string> = {
    success: "解析完成",
    failed: "解析失败",
    unsupported_ocr: "需要 OCR",
    pending: "等待解析",
    processing: "解析中",
  };
  return status === null ? "原始文件" : (labels[status] ?? status);
}

export function FileShelf({
  files,
  disabled,
  uploading,
  onUpload,
  onDelete,
}: FileShelfProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSelection = async (selected: FileList | null) => {
    if (selected === null || disabled) {
      return;
    }
    for (const file of Array.from(selected)) {
      await onUpload(file);
    }
    if (inputRef.current !== null) {
      inputRef.current.value = "";
    }
  };

  return (
    <section className="resource-section" aria-labelledby="uploads-title">
      <div className="resource-heading">
        <div>
          <span className="resource-index">INPUT / {String(files.length).padStart(2, "0")}</span>
          <h2 id="uploads-title">上传资料</h2>
        </div>
        <input
          ref={inputRef}
          hidden
          multiple
          type="file"
          accept={ACCEPTED_TYPES}
          disabled={disabled}
          aria-label="选择上传文件"
          onChange={(event) => void handleSelection(event.target.files)}
        />
        <Button
          size="small"
          icon={uploading ? <LoadingOutlined /> : <UploadOutlined />}
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? "处理中" : "上传"}
        </Button>
      </div>

      <div className="resource-list">
        {files.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="上传资料后可让 Agent 读取" />
        ) : (
          files.map((file) => (
            <article className="resource-card upload" key={file.id}>
              <span className="resource-icon" aria-hidden="true">
                <FileTextOutlined />
              </span>
              <div className="resource-copy">
                <Tooltip title={file.original_name}>
                  <strong>{file.original_name}</strong>
                </Tooltip>
                <small>
                  {formatSize(file.size_bytes)} · {file.extension?.slice(1).toUpperCase()}
                </small>
              </div>
              <Tag className={`parse-status ${file.parse_status ?? "unknown"}`}>
                {statusLabel(file.parse_status)}
              </Tag>
              <Popconfirm
                title="删除这个文件？"
                description="原文件和解析结果将一并删除。"
                okText="删除"
                cancelText="取消"
                disabled={disabled}
                onConfirm={() => void onDelete(file.id)}
              >
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  disabled={disabled}
                  aria-label={`删除 ${file.original_name}`}
                />
              </Popconfirm>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
