import { useState } from "react";
import type { Source } from "../types";

interface Props {
  sources: Source[];
}

export function SourcesPanel({ sources }: Props) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  return (
    <div className="sources">
      <button
        type="button"
        className="sources-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={`chevron ${open ? "open" : ""}`} aria-hidden="true">
          ▸
        </span>
        Sources ({sources.length})
      </button>
      {open && (
        <ul className="sources-list">
          {sources.map((s, i) => (
            <li key={i} className="source-item">
              <div className="source-head">
                <span className="source-title">{s.title}</span>
                <span className="source-tool">{s.tool}</span>
              </div>
              <p className="source-snippet">{s.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
