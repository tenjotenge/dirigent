import { invoke, isTauri } from "@tauri-apps/api/core";

export async function ensureBackendRunning(): Promise<TauriBackendStatus> {
  if (!isTauri()) {
    return {
      running: true,
      managed: false,
      message: "Running in browser — start backend manually",
      apiUrl: "http://127.0.0.1:8000",
    };
  }
  return invoke<TauriBackendStatus>("ensure_backend_running");
}

export async function getBackendProcessStatus(): Promise<TauriBackendStatus> {
  if (!isTauri()) {
    return {
      running: false,
      managed: false,
      message: "Browser mode",
      apiUrl: "http://127.0.0.1:8000",
    };
  }
  return invoke<TauriBackendStatus>("get_backend_status");
}

export async function pickRepositoryFolder(): Promise<string | null> {
  if (!isTauri()) {
    const path = window.prompt("Enter repository path:");
    return path?.trim() || null;
  }
  return invoke<string | null>("pick_repository_folder");
}
