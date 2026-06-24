export type WorkflowStatus =
  | "idle"
  | "sending"
  | "waiting_provider"
  | "evaluating_policy"
  | "executing_tool"
  | "completed"
  | "generating_long";  // Long-running generation in progress

export type ExecutionEventType =
  | "provider_request"
  | "provider_response"
  | "tool_request"
  | "policy_decision"
  | "tool_execution"
  | "error"
  | "success"
  | "info";

export interface ExecutionLogEntry {
  id: string;
  type: ExecutionEventType;
  message: string;
  timestamp: Date;
  details?: string;
  provider?: string;
  policyDecision?: string;
  tools?: string[];
  durationMs?: number;
  success?: boolean;
}

export interface ToolResultData {
  success: boolean;
  stdout?: string | null;
  stderr?: string | null;
  data?: Record<string, unknown> | null;
}

export interface ToolCallResult {
  call_id: string;
  success: boolean;
  tool_name?: string | null;
  args?: Record<string, unknown> | null;
  error?: string | null;
  result?: ToolResultData | null;
}

export interface PolicyCall {
  tool_name: string;
  call_id: string;
  args?: Record<string, unknown>;
  requires_confirmation?: boolean;
  reason?: string | null;
}

export interface PolicyDecision {
  allowed_calls: PolicyCall[];
  pending_confirmation_calls: PolicyCall[];
  blocked_calls: PolicyCall[];
  requires_user_confirmation: boolean;
  reasons: Record<string, string>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  toolResults?: ToolCallResult[];
  policyDecision?: PolicyDecision;
  error?: string;
}

export interface PendingAction {
  tool_name: string;
  call_id: string;
  args: Record<string, unknown>;
  reason?: string;
}

export interface BackendStatus {
  backendOnline: boolean;
  providerAvailable: boolean;
  repoPath: string;
  repoLoaded: boolean;
  lmstudioUrl: string;
  apiUrl: string;
  backendManaged: boolean;
}

export type AppView = "main" | "settings";

export type StartupPhase =
  | "initializing"
  | "starting_backend"
  | "waiting_backend"
  | "checking_health"
  | "connecting_lmstudio"
  | "loading_models"
  | "restoring_workspace"
  | "ready"
  | "error";

export interface GenerateResponse {
  response: string;
  tool_results?: ToolCallResult[] | null;
  policy_decision?: PolicyDecision | null;
  validation_errors?: string[] | null;
  metadata?: {
    model?: string;
    provider?: string;
    generation_time_seconds?: number;
    generation_state?: string;
    parse_method?: string;
    raw_output_length?: number;
  };
}
