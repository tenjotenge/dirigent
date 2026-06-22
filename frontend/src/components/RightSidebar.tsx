import { useEffect, useRef } from "react";
import type { ExecutionLogEntry } from "../types";
import { formatDuration, formatTimestamp } from "../utils/format";

interface RightSidebarProps {
  logs: ExecutionLogEntry[];
  onClear: () => void;
}

const EVENT_LABELS: Record<ExecutionLogEntry["type"], string> = {
  provider_request: "Provider",
  provider_response: "Provider",
  tool_request: "Tool",
  policy_decision: "Policy",
  tool_execution: "Execution",
  error: "Error",
  success: "Success",
  info: "Info",
};

export function RightSidebar({ logs, onClear }: RightSidebarProps) {
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <aside className="right-sidebar">
      <div className="right-sidebar-header">
        <h3>Execution Log</h3>
        <button className="btn-ghost btn-sm" onClick={onClear} type="button">
          Clear
        </button>
      </div>

      <div className="execution-log">
        {logs.length === 0 ? (
          <div className="empty-state small">
            Events will appear here as requests are processed.
          </div>
        ) : (
          logs.map((log) => (
            <div
              key={log.id}
              className={`log-entry log-${log.type} ${log.success === false ? "log-failed" : ""}`}
            >
              <div className="log-entry-header">
                <span className="log-entry-type">{EVENT_LABELS[log.type]}</span>
                <span className="log-entry-time">{formatTimestamp(log.timestamp)}</span>
              </div>
              <div className="log-entry-message">{log.message}</div>
              <div className="log-entry-meta">
                {log.provider && (
                  <span className="log-meta-tag">Provider: {log.provider}</span>
                )}
                {log.policyDecision && (
                  <span className="log-meta-tag">Policy: {log.policyDecision}</span>
                )}
                {log.tools && log.tools.length > 0 && (
                  <span className="log-meta-tag">Tools: {log.tools.join(", ")}</span>
                )}
                {log.durationMs !== undefined && (
                  <span className="log-meta-tag">{formatDuration(log.durationMs)}</span>
                )}
                {log.success !== undefined && (
                  <span className={`log-meta-tag ${log.success ? "meta-ok" : "meta-err"}`}>
                    {log.success ? "Success" : "Failed"}
                  </span>
                )}
              </div>
              {log.details && (
                <details className="log-entry-details">
                  <summary>Details</summary>
                  <pre>{log.details}</pre>
                </details>
              )}
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </aside>
  );
}
