import { ExportOutlined } from "@ant-design/icons";

import type { SourceReference } from "../types/api";

interface SourceReferencesProps {
  sources: SourceReference[];
}

export function SourceReferences({ sources }: SourceReferencesProps) {
  if (sources.length === 0) {
    return null;
  }

  return (
    <section className="source-references" aria-label="参考来源">
      <div className="source-heading">
        <span>REFERENCES</span>
        <span>{sources.length.toString().padStart(2, "0")}</span>
      </div>
      <ol>
        {sources.map((source) => (
          <li key={source.url}>
            <a href={source.url} target="_blank" rel="noreferrer noopener">
              <span>{source.title}</span>
              <ExportOutlined aria-hidden="true" />
            </a>
            {source.snippet && <p>{source.snippet}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}
