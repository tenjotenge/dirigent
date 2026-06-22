import { useState } from "react";
import type { ToolCallResult } from "../types";
import { formatArgs } from "../utils/format";

interface ToolExecutionCardProps {
  result: ToolCallResult;
}

export function ToolExecutionCard({ result }: ToolExecutionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const status = result.success ? "Completed" : "Failed";

  return (
    <div className={`tool-card ${result.success ? "success" : "failed"}`}>
      <button
        className="tool-card-header"
        onClick={() => setExpanded(!expanded)}
        type="button"
      >
        <span className="tool-card-name">{result.tool_name ?? "unknown_tool"}</span>
        <span className={`tool-card-status status-${result.success ? "ok" : "err"}`}>
          {status}
        </span>
        <span className="tool-card-chevron">{expanded ? "▾" : "▸"}</span>
      </button>

      {expanded && (
        <div className="tool-card-body">
          <div className="tool-card-section">
            <div className="tool-card-label">Arguments</div>
            <pre className="tool-card-pre">{formatArgs(result.args ?? undefined)}</pre>
          </div>

          {result.error && (
            <div className="tool-card-section">
              <div className="tool-card-label">Error</div>
              <pre className="tool-card-pre error-text">{result.error}</pre>
            </div>
          )}

          {result.result?.stdout && (
            <div className="tool-card-section">
              <div className="tool-card-label">stdout</div>
              <pre className="tool-card-pre">{result.result.stdout}</pre>
            </div>
          )}

          {result.result?.stderr && (
            <div className="tool-card-section">
              <div className="tool-card-label">stderr</div>
              <pre className="tool-card-pre">{result.result.stderr}</pre>
            </div>
          )}

          {result.result?.data && Object.keys(result.result.data).length > 0 && (
            <div className="tool-card-section">
              <div className="tool-card-label">Result</div>
              <pre className="tool-card-pre">
                {JSON.stringify(result.result.data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
