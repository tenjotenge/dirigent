import { computeLineDiff, truncate } from "../utils/diff";

interface WritePreviewProps {
  filePath: string;
  existingContent: string | null;
  proposedContent: string;
}

export function WritePreview({
  filePath,
  existingContent,
  proposedContent,
}: WritePreviewProps) {
  const isNewFile = existingContent === null;
  const diff = existingContent !== null
    ? computeLineDiff(existingContent, proposedContent)
    : null;

  return (
    <div className="write-preview">
      <div className="write-preview-path">
        <span className="write-preview-label">Target path</span>
        <code>{filePath}</code>
      </div>

      {isNewFile ? (
        <div className="write-preview-section">
          <div className="write-preview-label">New file preview</div>
          <pre className="write-preview-content">{truncate(proposedContent)}</pre>
        </div>
      ) : diff ? (
        <div className="write-preview-diff">
          <div className="write-preview-label">Changes</div>
          <pre className="diff-view">
            {diff.map((line, i) => (
              <div key={i} className={`diff-line diff-${line.type}`}>
                <span className="diff-marker">
                  {line.type === "add" ? "+" : line.type === "remove" ? "-" : " "}
                </span>
                {line.content}
              </div>
            ))}
          </pre>
        </div>
      ) : (
        <div className="write-preview-columns">
          <div className="write-preview-section">
            <div className="write-preview-label">Existing content</div>
            <pre className="write-preview-content">{truncate(existingContent ?? "")}</pre>
          </div>
          <div className="write-preview-section">
            <div className="write-preview-label">Proposed content</div>
            <pre className="write-preview-content">{truncate(proposedContent)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
