import { useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";
import {
  executeConfirmedTool,
  fetchHealth,
  fetchModels,
  fetchSettings,
  generate,
  gitStatus,
  setApiBase,
  setWorkspace,
  type SettingsResponse,
} from "./api/client";
import { CenterPanel } from "./components/CenterPanel";
import { ConfirmationModal } from "./components/ConfirmationModal";
import { LeftSidebar } from "./components/LeftSidebar";
import { RightSidebar } from "./components/RightSidebar";
import { SettingsView } from "./components/SettingsView";
import { StartupSplash } from "./components/StartupSplash";
import { useExecutionLog } from "./hooks/useExecutionLog";
import {
  addRecentRepo,
  loadPreferences,
  loadRecentRepos,
  loadSelectedModel,
  savePreferences,
  saveSelectedModel,
  type UserPreferences,
} from "./services/storage";
import { ensureBackendRunning, pickRepositoryFolder } from "./services/tauri";
import type {
  AppView,
  BackendStatus,
  ChatMessage,
  PendingAction,
  PolicyDecision,
  StartupPhase,
  ToolCallResult,
  WorkflowStatus,
} from "./types";
import { affectedFiles, formatArgs } from "./utils/format";

let messageCounter = 0;

function nextMessageId() {
  return `msg-${++messageCounter}-${Date.now()}`;
}

function App() {
  const { logs, addLog, clearLogs } = useExecutionLog();

  const [startupPhase, setStartupPhase] = useState<StartupPhase>("initializing");
  const [startupMessage, setStartupMessage] = useState("Preparing Dirigent…");
  const [startupError, setStartupError] = useState<string | undefined>();
  const [currentView, setCurrentView] = useState<AppView>("main");

  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState(loadSelectedModel);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>("idle");
  const [isRefreshingModels, setIsRefreshingModels] = useState(false);
  const [isOpeningRepo, setIsOpeningRepo] = useState(false);
  const [pendingQueue, setPendingQueue] = useState<PendingAction[]>([]);
  const [isConfirming, setIsConfirming] = useState(false);
  const [recentRepos, setRecentRepos] = useState(loadRecentRepos);
  const [preferences, setPreferences] = useState<UserPreferences>(loadPreferences);
  const [appSettings, setAppSettings] = useState<SettingsResponse | null>(null);
  const [backendDiagnostics, setBackendDiagnostics] = useState("");

  const [backendStatus, setBackendStatus] = useState<BackendStatus>({
    backendOnline: false,
    providerAvailable: false,
    repoPath: "",
    repoLoaded: false,
    lmstudioUrl: "http://127.0.0.1:1234",
    apiUrl: "http://127.0.0.1:8000",
    backendManaged: false,
  });

  const isBusy =
    workflowStatus !== "idle" || isConfirming || pendingQueue.length > 0;

  const refreshStatus = useCallback(async () => {
    try {
      const health = await fetchHealth();
      setBackendStatus({
        backendOnline: true,
        providerAvailable: health.provider_available,
        repoPath: health.repo_path,
        repoLoaded: health.repo_loaded,
        lmstudioUrl: health.lmstudio_url,
        apiUrl: health.api_url,
        backendManaged: backendStatus.backendManaged,
      });
      return health;
    } catch (error) {
      setBackendStatus((prev) => ({
        ...prev,
        backendOnline: false,
        providerAvailable: false,
        repoLoaded: false,
      }));
      throw error;
    }
  }, [backendStatus.backendManaged]);

  const loadModels = useCallback(async () => {
    setIsRefreshingModels(true);
    const start = performance.now();
    try {
      const modelList = await fetchModels();
      setModels(modelList);

      if (modelList.length === 0) {
        addLog("error", "No models returned from LM Studio", {
          provider: "lmstudio",
          success: false,
          durationMs: Math.round(performance.now() - start),
        });
        return modelList;
      }

      setSelectedModel((current) => {
        if (current && modelList.includes(current)) return current;
        const next = modelList[0];
        saveSelectedModel(next);
        return next;
      });

      addLog("success", `Loaded ${modelList.length} model(s)`, {
        provider: "lmstudio",
        success: true,
        durationMs: Math.round(performance.now() - start),
      });
      return modelList;
    } catch (error) {
      addLog("error", "Failed to load models", {
        provider: "lmstudio",
        details: error instanceof Error ? error.message : String(error),
        success: false,
        durationMs: Math.round(performance.now() - start),
      });
      return [];
    } finally {
      setIsRefreshingModels(false);
    }
  }, [addLog]);

  const openRepository = useCallback(
    async (path?: string) => {
      setIsOpeningRepo(true);
      try {
        const selected = path ?? (await pickRepositoryFolder());
        if (!selected) return;

        const workspace = await setWorkspace(selected);
        const updated = addRecentRepo(selected);
        setRecentRepos(updated);

        setBackendStatus((prev) => ({
          ...prev,
          repoPath: workspace.repo_path,
          repoLoaded: workspace.repo_loaded,
        }));

        addLog("success", `Opened repository: ${workspace.repo_path}`, {
          success: true,
        });
      } catch (error) {
        addLog("error", "Failed to open repository", {
          details: error instanceof Error ? error.message : String(error),
          success: false,
        });
      } finally {
        setIsOpeningRepo(false);
      }
    },
    [addLog],
  );

  useEffect(() => {
    let cancelled = false;

    async function startup() {
      try {
        setStartupPhase("starting_backend");
        setStartupMessage("Checking backend…");

        const backend = await ensureBackendRunning();
        if (cancelled) return;

        setApiBase(backend.apiUrl);
        setBackendDiagnostics(
          [
            `API URL: ${backend.apiUrl}`,
            `Managed by Dirigent: ${backend.managed ? "yes" : "no"}`,
            `Status: ${backend.message}`,
          ].join("\n"),
        );

        if (!backend.running) {
          setStartupPhase("error");
          setStartupError(backend.message);
          return;
        }

        setBackendStatus((prev) => ({
          ...prev,
          backendOnline: true,
          backendManaged: backend.managed,
          apiUrl: backend.apiUrl,
        }));

        setStartupPhase("checking_health");
        setStartupMessage("Verifying backend health…");
        const health = await fetchHealth();
        if (cancelled) return;

        addLog("info", "Backend connection verified", {
          success: true,
          durationMs: 0,
        });

        setStartupPhase("loading_models");
        setStartupMessage("Loading models from LM Studio…");

        const settings = await fetchSettings();
        setAppSettings(settings);

        setBackendStatus({
          backendOnline: true,
          providerAvailable: health.provider_available,
          repoPath: health.repo_path,
          repoLoaded: health.repo_loaded,
          lmstudioUrl: health.lmstudio_url,
          apiUrl: health.api_url,
          backendManaged: backend.managed,
        });

        await loadModels();
        if (cancelled) return;

        setStartupPhase("restoring_workspace");
        setStartupMessage(
          health.repo_loaded
            ? `Restored workspace: ${health.repo_path}`
            : "No workspace selected — open a repository to begin",
        );

        await new Promise((r) => setTimeout(r, 400));
        if (cancelled) return;

        setStartupPhase("ready");
      } catch (error) {
        if (!cancelled) {
          setStartupPhase("error");
          setStartupError(
            error instanceof Error ? error.message : String(error),
          );
        }
      }
    }

    startup();
    return () => {
      cancelled = true;
    };
  }, [addLog, loadModels]);

  useEffect(() => {
    if (startupPhase !== "ready") return;
    refreshStatus().catch(() => undefined);
    const interval = setInterval(() => {
      refreshStatus().catch(() => undefined);
    }, 30000);
    return () => clearInterval(interval);
  }, [startupPhase, refreshStatus]);

  const handleModelChange = (model: string) => {
    setSelectedModel(model);
    saveSelectedModel(model);
  };

  const handlePreferencesChange = (prefs: UserPreferences) => {
    setPreferences(prefs);
    savePreferences(prefs);
  };

  const logPolicyDecision = (policy: PolicyDecision) => {
    for (const call of policy.allowed_calls) {
      addLog("policy_decision", `✓ ${call.tool_name} approved`, {
        policyDecision: "approved",
        tools: [call.tool_name],
        details: call.reason ?? undefined,
        success: true,
      });
    }
    for (const call of policy.pending_confirmation_calls) {
      addLog("policy_decision", `⚠ ${call.tool_name} requires confirmation`, {
        policyDecision: "confirmation_required",
        tools: [call.tool_name],
        details: call.reason ?? undefined,
      });
    }
    for (const call of policy.blocked_calls) {
      addLog("policy_decision", `✕ ${call.tool_name} denied`, {
        policyDecision: "denied",
        tools: [call.tool_name],
        details: call.reason ?? undefined,
        success: false,
      });
    }
  };

  const logToolResults = (results: ToolCallResult[], durationMs?: number) => {
    for (const result of results) {
      addLog(
        result.success ? "tool_execution" : "error",
        `${result.tool_name ?? "tool"} ${result.success ? "completed" : "failed"}`,
        {
          tools: result.tool_name ? [result.tool_name] : undefined,
          details: formatArgs({
            args: result.args,
            stdout: result.result?.stdout,
            stderr: result.result?.stderr ?? result.error,
          }),
          success: result.success,
          durationMs,
        },
      );
    }
  };

  const enqueuePendingActions = (policy: PolicyDecision) => {
    const pending: PendingAction[] = policy.pending_confirmation_calls.map(
      (call) => ({
        tool_name: call.tool_name,
        call_id: call.call_id,
        args: call.args ?? {},
        reason: call.reason ?? policy.reasons[call.call_id],
      }),
    );
    if (pending.length > 0) {
      setPendingQueue((prev) => [...prev, ...pending]);
    }
  };

  const handleGenerate = async () => {
    if (!chatInput.trim() || !selectedModel || !backendStatus.repoLoaded) return;

    const userMessage = chatInput.trim();
    setMessages((prev) => [
      ...prev,
      {
        id: nextMessageId(),
        role: "user",
        content: userMessage,
        timestamp: new Date(),
      },
    ]);
    setChatInput("");

    const start = performance.now();
    setWorkflowStatus("sending");
    addLog("provider_request", `Sending prompt to ${selectedModel}`, {
      provider: "lmstudio",
      details: userMessage,
    });

    try {
      setWorkflowStatus("waiting_provider");
      const data = await generate({ model: selectedModel, prompt: userMessage });
      const providerDuration = Math.round(performance.now() - start);

      addLog("provider_response", `Received response from ${selectedModel}`, {
        provider: "lmstudio",
        success: true,
        durationMs: providerDuration,
      });

      if (data.policy_decision) {
        setWorkflowStatus("evaluating_policy");
        logPolicyDecision(data.policy_decision);
        enqueuePendingActions(data.policy_decision);
      }

      if (data.tool_results && data.tool_results.length > 0) {
        setWorkflowStatus("executing_tool");
        logToolResults(
          data.tool_results,
          Math.round(performance.now() - start),
        );
      }

      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId(),
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
          toolResults: data.tool_results ?? undefined,
          policyDecision: data.policy_decision ?? undefined,
        },
      ]);

      setWorkflowStatus("completed");
      addLog("success", "Request completed", {
        provider: "lmstudio",
        success: true,
        durationMs: Math.round(performance.now() - start),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId(),
          role: "assistant",
          content: "",
          timestamp: new Date(),
          error: message,
        },
      ]);
      addLog("error", "Generation failed", {
        provider: "lmstudio",
        details: message,
        success: false,
        durationMs: Math.round(performance.now() - start),
      });
    } finally {
      setTimeout(() => setWorkflowStatus("idle"), 800);
    }
  };

  const handleGitStatus = async () => {
    const start = performance.now();
    setWorkflowStatus("executing_tool");
    addLog("tool_request", "git_status requested", { tools: ["git_status"] });

    try {
      const data = await gitStatus();
      const output = data.stdout || data.stderr || data.error || "No output";

      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId(),
          role: "assistant",
          content: `\`\`\`\n${output}\n\`\`\``,
          timestamp: new Date(),
          toolResults: [
            {
              call_id: nextMessageId(),
              success: data.success,
              tool_name: "git_status",
              args: {},
              error: data.error,
              result: {
                success: data.success,
                stdout: data.stdout,
                stderr: data.stderr,
              },
            },
          ],
        },
      ]);

      addLog(
        data.success ? "success" : "error",
        data.success ? "git_status completed" : "git_status failed",
        {
          tools: ["git_status"],
          details: output,
          success: data.success,
          durationMs: Math.round(performance.now() - start),
        },
      );
    } catch (error) {
      addLog("error", "git_status failed", {
        tools: ["git_status"],
        details: error instanceof Error ? error.message : String(error),
        success: false,
        durationMs: Math.round(performance.now() - start),
      });
    } finally {
      setWorkflowStatus("idle");
    }
  };

  const handleClearConversation = () => {
    setMessages([]);
    addLog("info", "Conversation cleared");
  };

  const handleConfirmAction = async () => {
    const action = pendingQueue[0];
    if (!action) return;

    setIsConfirming(true);
    setWorkflowStatus("executing_tool");
    const start = performance.now();
    const files = affectedFiles(action.tool_name, action.args);

    addLog("tool_request", `Executing confirmed ${action.tool_name}`, {
      tools: [action.tool_name],
      details: formatArgs(action.args),
      policyDecision: "user_confirmed",
    });

    try {
      const result = await executeConfirmedTool(action.tool_name, action.args);
      const toolResult: ToolCallResult = {
        call_id: action.call_id,
        success: result.success,
        tool_name: action.tool_name,
        args: action.args,
        error: result.error ?? result.stderr,
        result: {
          success: result.success,
          stdout: result.stdout,
          stderr: result.stderr,
        },
      };

      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId(),
          role: "assistant",
          content: result.success
            ? `Confirmed \`${action.tool_name}\` completed successfully.${files.length ? ` Affected: ${files.join(", ")}` : ""}`
            : `Confirmed \`${action.tool_name}\` failed.`,
          timestamp: new Date(),
          toolResults: [toolResult],
          error: result.success ? undefined : (result.error ?? result.stderr ?? "Unknown error"),
        },
      ]);

      addLog(
        result.success ? "success" : "error",
        `${action.tool_name} ${result.success ? "completed" : "failed"}`,
        {
          tools: [action.tool_name],
          details: result.stdout ?? result.stderr ?? result.error,
          policyDecision: "user_confirmed",
          success: result.success,
          durationMs: Math.round(performance.now() - start),
        },
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId(),
          role: "assistant",
          content: "",
          timestamp: new Date(),
          error: message,
        },
      ]);
      addLog("error", `${action.tool_name} failed`, {
        tools: [action.tool_name],
        details: message,
        success: false,
        durationMs: Math.round(performance.now() - start),
      });
    } finally {
      setPendingQueue((prev) => prev.slice(1));
      setIsConfirming(false);
      setWorkflowStatus("idle");
    }
  };

  const handleCancelAction = () => {
    const action = pendingQueue[0];
    if (action) {
      addLog("info", `Cancelled ${action.tool_name} — no changes made`, {
        tools: [action.tool_name],
        policyDecision: "user_cancelled",
        details: action.call_id,
      });
    }
    setPendingQueue((prev) => prev.slice(1));
  };

  const handleRefreshStatus = async () => {
    try {
      await refreshStatus();
      addLog("info", "Status refreshed", { success: true });
    } catch (error) {
      addLog("error", "Backend unreachable", {
        details: error instanceof Error ? error.message : String(error),
        success: false,
      });
    }
  };

  const settingsContent = useMemo(
    () => (
      <SettingsView
        status={backendStatus}
        settings={appSettings}
        preferences={preferences}
        recentRepos={recentRepos}
        onBack={() => setCurrentView("main")}
        onPreferencesChange={handlePreferencesChange}
        onSettingsUpdated={setAppSettings}
        onOpenRepository={() => openRepository()}
        onSelectRecentRepo={(path) => openRepository(path)}
        backendDiagnostics={backendDiagnostics}
      />
    ),
    [
      backendStatus,
      appSettings,
      preferences,
      recentRepos,
      backendDiagnostics,
      openRepository,
    ],
  );

  if (startupPhase !== "ready") {
    return (
      <StartupSplash
        phase={startupPhase}
        message={startupMessage}
        error={startupError}
      />
    );
  }

  if (currentView === "settings") {
    return <div className="app app-settings">{settingsContent}</div>;
  }

  return (
    <div className="app">
      <LeftSidebar
        status={backendStatus}
        models={models}
        selectedModel={selectedModel}
        onModelChange={handleModelChange}
        onRefreshModels={loadModels}
        onRefreshStatus={handleRefreshStatus}
        onGitStatus={handleGitStatus}
        onClearConversation={handleClearConversation}
        onOpenRepository={() => openRepository()}
        onOpenSettings={() => setCurrentView("settings")}
        isBusy={workflowStatus !== "idle"}
        isRefreshingModels={isRefreshingModels}
        isOpeningRepo={isOpeningRepo}
      />

      <CenterPanel
        messages={messages}
        chatInput={chatInput}
        onChatInputChange={setChatInput}
        onSend={handleGenerate}
        isBusy={isBusy}
        workflowStatus={workflowStatus}
        selectedModel={selectedModel}
        repoLoaded={backendStatus.repoLoaded}
        onOpenRepository={() => openRepository()}
        isOpeningRepo={isOpeningRepo}
      />

      <RightSidebar logs={logs} onClear={clearLogs} />

      {pendingQueue[0] && (
        <ConfirmationModal
          action={pendingQueue[0]}
          onConfirm={handleConfirmAction}
          onCancel={handleCancelAction}
          isExecuting={isConfirming}
        />
      )}
    </div>
  );
}

export default App;
