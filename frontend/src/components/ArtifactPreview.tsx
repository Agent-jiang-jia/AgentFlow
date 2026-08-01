import { Alert, Modal, Spin } from "antd";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import {
  artifactPreviewUrl,
  fetchArtifactText,
} from "../api/artifacts";
import type { FileMetadata } from "../types/api";
import { parseCsvPreview } from "../utils/csv";

interface ArtifactPreviewProps {
  threadId: string;
  artifact: FileMetadata;
  onClose: () => void;
}

const CODE_LANGUAGES: Record<string, string> = {
  ".json": "json",
  ".py": "python",
  ".js": "javascript",
  ".ts": "typescript",
  ".yaml": "yaml",
  ".yml": "yaml",
};

function fencedCode(content: string, language: string): string {
  const longest = Math.max(
    2,
    ...Array.from(content.matchAll(/`+/g), (match) => match[0].length),
  );
  const fence = "`".repeat(longest + 1);
  return `${fence}${language}\n${content}\n${fence}`;
}

function normalizeJson(content: string): string {
  try {
    const parsed: unknown = JSON.parse(content);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return content;
  }
}

export default function ArtifactPreview({
  threadId,
  artifact,
  onClose,
}: ArtifactPreviewProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isHtml = artifact.extension === ".html";

  useEffect(() => {
    if (isHtml) {
      return;
    }
    const controller = new AbortController();
    void fetchArtifactText(threadId, artifact.id, controller.signal)
      .then(setContent)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "成果预览失败");
        }
      });
    return () => controller.abort();
  }, [artifact.id, isHtml, threadId]);

  const csv = useMemo(
    () => (artifact.extension === ".csv" && content !== null ? parseCsvPreview(content) : null),
    [artifact.extension, content],
  );
  const codeLanguage =
    artifact.extension === null ? undefined : CODE_LANGUAGES[artifact.extension];

  let preview = <Spin tip="正在读取成果" />;
  if (isHtml) {
    preview = (
      <iframe
        className="html-artifact-frame"
        src={artifactPreviewUrl(threadId, artifact.id)}
        sandbox=""
        title={`${artifact.original_name} 受限预览`}
      />
    );
  } else if (error !== null) {
    preview = <Alert type="error" showIcon title={error} />;
  } else if (content !== null && artifact.extension === ".md") {
    preview = (
      <div className="artifact-markdown markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
          {content}
        </ReactMarkdown>
      </div>
    );
  } else if (content !== null && csv !== null) {
    preview = (
      <div className="csv-preview">
        {csv.truncated && <p>预览前 500 行；下载可查看完整文件。</p>}
        <table>
          <tbody>
            {csv.rows.map((row, rowIndex) => (
              <tr key={`${rowIndex}-${row.join("|")}`}>
                {row.map((cell, cellIndex) =>
                  rowIndex === 0 ? (
                    <th key={cellIndex}>{cell}</th>
                  ) : (
                    <td key={cellIndex}>{cell}</td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  } else if (content !== null && codeLanguage !== undefined) {
    const normalized = artifact.extension === ".json" ? normalizeJson(content) : content;
    preview = (
      <div className="artifact-code markdown-body">
        <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
          {fencedCode(normalized, codeLanguage)}
        </ReactMarkdown>
      </div>
    );
  } else if (content !== null) {
    preview = <pre className="plain-preview">{content}</pre>;
  }

  return (
    <Modal
      open
      width="min(960px, calc(100vw - 32px))"
      footer={null}
      destroyOnHidden
      title={artifact.original_name}
      className="artifact-preview-modal"
      onCancel={onClose}
    >
      <div className="artifact-preview-body">{preview}</div>
    </Modal>
  );
}
