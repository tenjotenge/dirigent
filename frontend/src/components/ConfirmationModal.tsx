import { useEffect, useState } from "react";
import { readFile } from "../api/client";
import type { PendingAction } from "../types";
import { affectedFiles, formatArgs } from "../utils/format";
import { WritePreview } from "./WritePreview";

interface ConfirmationModalProps {
  action: PendingAction;
  onConfirm: () => void;
  onCancel: () => void;
  isExecuting: boolean;
}

export function ConfirmationModal({
  action,
  onConfirm,
  onCancel,
  isExecuting,
}: ConfirmationModalProps) {
  const [existingContent, setExistingContent] = useState<string | null | undefined>(
    undefined,
  );
  const files = affectedFiles(action.tool_name, action.args);
  const isWrite = action.tool_name === "write_file";

  useEffect(() => {
    if (!isWrite) {
      setExistingContent(undefined);
      return;
    }

    const filePath = String(action.args.file_path ?? "");
    if (!filePath) {
      setExistingContent(null);
      return;
    }

    let cancelled = false;
    readFile(filePath)
      .then((result) => {
        if (cancelled) return;
        setExistingContent(result.success ? (result.content ?? "") : null);
      })
      .catch(() => {
        if (!cancelled) setExistingContent(null);
      });

    return () => {
      cancelled = true;
    };
  }, [action, isWrite]);

  return (
    <div
      className="modal-overlay"
      onClick={isExecuting ? undefined : onCancel}
    >
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Confirm action</h3>
          <p className="modal-subtitle">
            This operation requires your approval before execution.
          </p>
        </div>

        <div className="modal-body">
          <div className="confirm-detail">
            <span className="confirm-label">Action</span>
            <code className="confirm-value">{action.tool_name}</code>
          </div>

          {action.reason && (
            <div className="confirm-detail">
              <span className="confirm-label">Policy</span>
              <span className="confirm-value">{action.reason}</span>
            </div>
          )}

          {files.length > 0 && (
            <div className="confirm-detail">
              <span className="confirm-label">Affected files</span>
              <ul className="confirm-files">
                {files.map((f) => (
                  <li key={f}><code>{f}</code></li>
                ))}
              </ul>
            </div>
          )}

          {isWrite && existingContent === undefined && (
            <div className="confirm-detail">
              <span className="confirm-label">Preview</span>
              <span className="confirm-value">Loading file preview…</span>
            </div>
          )}

          {isWrite && existingContent !== undefined && (
            <WritePreview
              filePath={String(action.args.file_path ?? "")}
              existingContent={existingContent}
              proposedContent={String(action.args.content ?? "")}
            />
          )}

          {!isWrite && (
            <div className="confirm-detail">
              <span className="confirm-label">Arguments</span>
              <pre className="confirm-args">{formatArgs(action.args)}</pre>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button
            className="btn-secondary"
            onClick={onCancel}
            disabled={isExecuting}
            type="button"
          >
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={onConfirm}
            disabled={isExecuting || (isWrite && existingContent === undefined)}
            type="button"
          >
            {isExecuting ? "Executing…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
