import { getApiBase } from "../config";
import type { GenerateResponse, PolicyDecision, ToolCallResult } from "../types";

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

export interface ChatGPTAuthResponse {
  status: "idle" | "pending" | "connected" | "failed";
  message?: string | null;
  connected: Array<{ id: string; email?: string | null; plan_enabled: boolean }>;
}

export interface ProviderCredentialStatus {
  id: "claude" | "cursor" | "devin";
  label: string;
  credential_label: string;
  env_var: string;
  hint: string;
  connected: boolean;
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

export async function fetchChatGPTAuthStatus(): Promise<ChatGPTAuthResponse> {
  return request<ChatGPTAuthResponse>("/auth/chatgpt");
}

export async function startChatGPTAuth(): Promise<ChatGPTAuthResponse> {
  return request<ChatGPTAuthResponse>("/auth/chatgpt/start", {
    method: "POST",
  });
}

export async function fetchProviderCredentialStatus(): Promise<ProviderCredentialStatus[]> {
  return request<ProviderCredentialStatus[]>("/auth/providers");
}

export async function saveProviderCredential(
  provider: ProviderCredentialStatus["id"],
  secret: string,
): Promise<ProviderCredentialStatus> {
  return request<ProviderCredentialStatus>(`/auth/providers/${provider}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ secret }),
  });
}

export async function deleteProviderCredential(
  provider: ProviderCredentialStatus["id"],
): Promise<void> {
  await request<unknown>(`/auth/providers/${provider}`, { method: "DELETE" });
}

export async function fetchModels(provider = "lmstudio"): Promise<string[]> {
  const data = await request<{ models: string[] }>(`/models?provider=${encodeURIComponent(provider)}`);
  return data.models;
}

export async function generate(params: {
  provider?: "lmstudio" | "chatgpt";
  model: string;
  prompt: string;
  conversation_id?: string | null;
  effort?: string | null;
  temperature?: number;
  max_tokens?: number;
}): Promise<GenerateResponse> {
  return request<GenerateResponse>("/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export interface ArchiveSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  run_count: number;
  last_provider: string | null;
  last_model: string | null;
  last_effort: string | null;
}

export interface ArchivedMessage {
  id: string;
  run_id: string | null;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  provider: string | null;
  model: string | null;
  effort: string | null;
  error: string | null;
  metadata: Record<string, unknown>;
}

export interface ArchivedConversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ArchivedMessage[];
  runs: Array<{
    id: string;
    tool_results: ToolCallResult[];
    policy_decision: PolicyDecision | null;
  }>;
}

export async function fetchArchiveSummaries(search = "", offset = 0): Promise<ArchiveSummary[]> {
  return request<ArchiveSummary[]>(`/archive/conversations?search=${encodeURIComponent(search)}&offset=${offset}`);
}

export async function fetchArchivedConversation(id: string): Promise<ArchivedConversation> {
  return request<ArchivedConversation>(`/archive/conversations/${encodeURIComponent(id)}`);
}

export async function importArchive(payload: unknown): Promise<{conversations: number; messages: number; runs: number}> {
  return request("/archive/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function archiveLocalAction(params: {
  conversation_id: string | null;
  prompt: string;
  response: string;
  error?: string;
  duration_ms: number;
  tool_results?: unknown[];
}): Promise<{conversation_id: string}> {
  return request("/archive/actions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export async function downloadArchive(path: string, filename: string): Promise<void> {
  const response = await fetch(`${apiBase}${path}`);
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
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
