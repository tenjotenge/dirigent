export interface DiffLine {
  type: "same" | "add" | "remove";
  content: string;
}

const PREVIEW_LIMIT = 2000;

export function truncate(text: string, limit = PREVIEW_LIMIT): string {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}\n\n… (${text.length - limit} more characters)`;
}

export function computeLineDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const result: DiffLine[] = [];

  const maxLen = Math.max(oldLines.length, newLines.length);
  for (let i = 0; i < maxLen; i++) {
    const oldLine = oldLines[i];
    const newLine = newLines[i];

    if (oldLine === newLine) {
      if (oldLine !== undefined) {
        result.push({ type: "same", content: oldLine });
      }
    } else {
      if (oldLine !== undefined) {
        result.push({ type: "remove", content: oldLine });
      }
      if (newLine !== undefined) {
        result.push({ type: "add", content: newLine });
      }
    }
  }

  return result;
}
