import {
  DeleteOutlined,
  FileTextOutlined,
  LoadingOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { Button, Empty, Tag, Tooltip, Typography } from "antd";
import { useRef } from "react";

import type { FileMetadata } from "../types/api";

const ACCEPTED_TYPES = ".pdf,.docx,.txt,.md,.csv";

interface FileShelfProps {
  files: FileMetadata[];
  disabled: boolean;
  uploading: boolean;
  onUpload: (file: File) => Promise<void>;
  onDelete: (fileId: string) => Promise<void>;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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
    <section className="file-shelf" aria-label="会话文件">
      <div className="file-shelf-heading">
        <div>
          <Typography.Text className="section-label">
            FILES / UPLOADS
          </Typography.Text>
          <Typography.Text>{files.length} 个上传文件</Typography.Text>
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
          {uploading ? "文件处理中" : "上传文件"}
        </Button>
      </div>

      <div className="file-shelf-list">
        {files.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无上传文件" />
        ) : (
          files.map((file) => (
            <article className="file-chip" key={file.id}>
              <FileTextOutlined />
              <div className="file-chip-copy">
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
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                disabled={disabled}
                aria-label={`删除 ${file.original_name}`}
                onClick={() => void onDelete(file.id)}
              />
            </article>
          ))
        )}
      </div>
    </section>
  );
}
