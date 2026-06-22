import { MAX_RECENT_REPOS, STORAGE_KEYS } from "../config";

export interface UserPreferences {
  theme: "system" | "dark" | "light";
  confirmWrites: boolean;
  confirmGit: boolean;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  theme: "dark",
  confirmWrites: true,
  confirmGit: true,
};

export function loadPreferences(): UserPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.preferences);
    if (!raw) return { ...DEFAULT_PREFERENCES };
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function savePreferences(prefs: UserPreferences): void {
  localStorage.setItem(STORAGE_KEYS.preferences, JSON.stringify(prefs));
}

export function loadSelectedModel(): string {
  return localStorage.getItem(STORAGE_KEYS.selectedModel) ?? "";
}

export function saveSelectedModel(model: string): void {
  localStorage.setItem(STORAGE_KEYS.selectedModel, model);
}

export function loadRecentRepos(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.recentRepos);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((p) => typeof p === "string") : [];
  } catch {
    return [];
  }
}

export function addRecentRepo(path: string): string[] {
  const normalized = path.trim();
  if (!normalized) return loadRecentRepos();

  const updated = [
    normalized,
    ...loadRecentRepos().filter((p) => p !== normalized),
  ].slice(0, MAX_RECENT_REPOS);

  localStorage.setItem(STORAGE_KEYS.recentRepos, JSON.stringify(updated));
  return updated;
}
