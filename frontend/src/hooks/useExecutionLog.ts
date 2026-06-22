import { useCallback, useState } from "react";
import type { ExecutionEventType, ExecutionLogEntry } from "../types";

let logCounter = 0;

export interface LogOptions {
  details?: string;
  provider?: string;
  policyDecision?: string;
  tools?: string[];
  durationMs?: number;
  success?: boolean;
}

export function useExecutionLog() {
  const [logs, setLogs] = useState<ExecutionLogEntry[]>([]);

  const addLog = useCallback(
    (
      type: ExecutionEventType,
      message: string,
      options?: LogOptions | string,
    ) => {
      const opts: LogOptions =
        typeof options === "string" ? { details: options } : (options ?? {});

      const entry: ExecutionLogEntry = {
        id: `log-${++logCounter}-${Date.now()}`,
        type,
        message,
        timestamp: new Date(),
        details: opts.details,
        provider: opts.provider,
        policyDecision: opts.policyDecision,
        tools: opts.tools,
        durationMs: opts.durationMs,
        success: opts.success,
      };
      setLogs((prev) => [...prev, entry].slice(-200));
      return entry.id;
    },
    [],
  );

  const clearLogs = useCallback(() => setLogs([]), []);

  return { logs, addLog, clearLogs };
}
