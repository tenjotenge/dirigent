import { getApiBase } from "../config";
import type { GenerateResponse } from "../types";

let apiBase = getApiBase();

export function setApiBase(url: string): void {
  apiBase = url.replace(/\/$/, "");
}

export function getApiBaseUrl(): string {
  return apiBase;
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // use statusText
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export interface HealthResponse {
  status: string;
  provider_available: boolean;
  repo_path: string;
  repo_loaded: boolean;
  lmstudio_url: string;
  api_url: string;
  development_mode: boolean;
}

export interface WorkspaceResponse {
  repo_path: string;
  repo_loaded: boolean;
  exists: boolean;
  is_git_repo: boolean;
}

export interface SettingsResponse {
  lmstudio_host: string;
  lmstudio_port: number;
  lmstudio_url: string;
  api_host: string;
  api_port: number;
  api_url: string;
  repo_path: string;
  development_mode: boolean;
  recent_repos: string[];
}

export interface ConnectionTestResponse {
  success: boolean;
  message: string;
  models_count: number;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function fetchWorkspace(): Promise<WorkspaceResponse> {
  return request<WorkspaceResponse>("/workspace");
}

export async function setWorkspace(repoPath: string): Promise<WorkspaceResponse> {
  return request<WorkspaceResponse>("/workspace", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_path: repoPath }),
  });
}

export async function fetchSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>("/settings");
}

export async function updateSettings(updates: {
  lmstudio_host?: string;
  lmstudio_port?: number;
  api_host?: string;
  api_port?: number;
}): Promise<SettingsResponse> {
  return request<SettingsResponse>("/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export async function testLmStudioConnection(): Promise<ConnectionTestResponse> {
  return request<ConnectionTestResponse>("/settings/test-lmstudio", {
    method: "POST",
  });
}

export async function fetchModels(): Promise<string[]> {
  const data = await request<{ models: string[] }>("/models");
  return data.models;
}

export async function generate(params: {
  model: string;
  prompt: string;
  temperature?: number;
  max_tokens?: number;
}): Promise<GenerateResponse> {
  return request<GenerateResponse>("/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export async function readFile(filePath: string): Promise<{
  success: boolean;
  content?: string;
  error?: string;
}> {
  return request("/tools/filesystem/read", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
}

export async function writeFile(
  filePath: string,
  content: string,
): Promise<{ success: boolean; error?: string }> {
  return request("/tools/filesystem/write", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath, content }),
  });
}

export async function gitStatus(): Promise<{
  success: boolean;
  stdout?: string;
  stderr?: string;
  error?: string;
}> {
  return request("/tools/git/status", { method: "POST" });
}

export async function gitAdd(filePaths: string[]): Promise<{
  success: boolean;
  stdout?: string;
  stderr?: string;
  error?: string;
}> {
  return request("/tools/git/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_paths: filePaths }),
  });
}

export async function gitCommit(message: string): Promise<{
  success: boolean;
  stdout?: string;
  stderr?: string;
  error?: string;
}> {
  return request("/tools/git/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export async function gitPush(): Promise<{
  success: boolean;
  stdout?: string;
  stderr?: string;
  error?: string;
}> {
  return request("/tools/git/push", { method: "POST" });
}

export async function executeConfirmedTool(
  toolName: string,
  args: Record<string, unknown>,
): Promise<{ success: boolean; stdout?: string; stderr?: string; error?: string }> {
  switch (toolName) {
    case "write_file":
      return writeFile(String(args.file_path), String(args.content ?? ""));
    case "git_add":
      return gitAdd(Array.isArray(args.file_paths) ? (args.file_paths as string[]) : []);
    case "git_commit":
      return gitCommit(String(args.message ?? ""));
    case "git_push":
      return gitPush();
    default:
      throw new Error(`Unsupported tool: ${toolName}`);
  }
}
