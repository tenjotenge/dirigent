export function formatTimestamp(date: Date): string {
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatArgs(args: Record<string, unknown> | undefined | null): string {
  if (!args) return "{}";
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

export function affectedFiles(
  toolName: string,
  args: Record<string, unknown>,
): string[] {
  if (toolName === "write_file" && args.file_path) {
    return [String(args.file_path)];
  }
  if (toolName === "git_add" && Array.isArray(args.file_paths)) {
    return args.file_paths.map(String);
  }
  return [];
}

export function workflowStatusLabel(status: string): string {
  switch (status) {
    case "sending":
      return "Sending request…";
    case "waiting_provider":
      return "Waiting for provider…";
    case "evaluating_policy":
      return "Evaluating policy…";
    case "executing_tool":
      return "Executing tool…";
    case "completed":
      return "Completed";
    default:
      return "";
  }
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}
