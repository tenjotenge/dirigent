/** Centralized frontend configuration. */

const DEFAULT_API_HOST = "127.0.0.1";
const DEFAULT_API_PORT = 8000;

export function getApiBase(): string {
  const host = import.meta.env.VITE_API_HOST ?? DEFAULT_API_HOST;
  const port = import.meta.env.VITE_API_PORT ?? DEFAULT_API_PORT;
  return `http://${host}:${port}`;
}

export const STORAGE_KEYS = {
  selectedModel: "dirigent-selected-model",
  recentRepos: "dirigent-recent-repos",
  preferences: "dirigent-preferences",
  windowState: "dirigent-window-state",
} as const;

export const MAX_RECENT_REPOS = 8;
