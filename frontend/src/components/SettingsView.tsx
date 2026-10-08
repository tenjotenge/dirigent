import { useEffect, useState } from "react";
import type { BackendStatus } from "../types";
import {
  testLmStudioConnection,
  fetchChatGPTAuthStatus,
  fetchProviderCredentialStatus,
  saveProviderCredential,
  deleteProviderCredential,
  startChatGPTAuth,
  updateSettings,
  type ChatGPTAuthResponse,
  type ProviderCredentialStatus,
  type SettingsResponse,
} from "../api/client";
import type { UserPreferences } from "../services/storage";

interface SettingsViewProps {
  status: BackendStatus;
  settings: SettingsResponse | null;
  preferences: UserPreferences;
  recentRepos: string[];
  onBack: () => void;
  onPreferencesChange: (prefs: UserPreferences) => void;
  onSettingsUpdated: (settings: SettingsResponse) => void;
  onOpenRepository: () => void;
  onSelectRecentRepo: (path: string) => void;
  backendDiagnostics: string;
}

export function SettingsView({
  status,
  settings,
  preferences,
  recentRepos,
  onBack,
  onPreferencesChange,
  onSettingsUpdated,
  onOpenRepository,
  onSelectRecentRepo,
  backendDiagnostics,
}: SettingsViewProps) {
  const [lmHost, setLmHost] = useState(settings?.lmstudio_host ?? "127.0.0.1");
  const [lmPort, setLmPort] = useState(String(settings?.lmstudio_port ?? 1234));
  const [testResult, setTestResult] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [chatgptAuth, setChatgptAuth] = useState<ChatGPTAuthResponse | null>(null);
  const [isConnectingChatGPT, setIsConnectingChatGPT] = useState(false);
  const [providerCredentials, setProviderCredentials] = useState<ProviderCredentialStatus[]>([]);
  const [providerSecrets, setProviderSecrets] = useState<Record<string, string>>({});
  const [providerResult, setProviderResult] = useState<string | null>(null);

  useEffect(() => {
    fetchChatGPTAuthStatus().then(setChatgptAuth).catch(() => undefined);
    fetchProviderCredentialStatus().then(setProviderCredentials).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (chatgptAuth?.status !== "pending") return;
    const timer = window.setInterval(() => {
      fetchChatGPTAuthStatus().then(setChatgptAuth).catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [chatgptAuth?.status]);

  const handleSaveLmStudio = async () => {
    setIsSaving(true);
    try {
      const updated = await updateSettings({
        lmstudio_host: lmHost.trim(),
        lmstudio_port: parseInt(lmPort, 10) || 1234,
      });
      onSettingsUpdated(updated);
      setTestResult("Settings saved.");
    } catch (error) {
      setTestResult(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      await handleSaveLmStudio();
      const result = await testLmStudioConnection();
      setTestResult(result.message);
    } catch (error) {
      setTestResult(error instanceof Error ? error.message : String(error));
    } finally {
      setIsTesting(false);
    }
  };

  const handleConnectChatGPT = async () => {
    setIsConnectingChatGPT(true);
    try {
      setChatgptAuth(await startChatGPTAuth());
    } catch (error) {
      setChatgptAuth({
        status: "failed",
        message: error instanceof Error ? error.message : String(error),
        connected: [],
      });
    } finally {
      setIsConnectingChatGPT(false);
    }
  };

  const handleSaveProvider = async (provider: ProviderCredentialStatus) => {
    const secret = providerSecrets[provider.id] ?? "";
    if (!secret.trim()) return;
    try {
      const updated = await saveProviderCredential(provider.id, secret);
      setProviderCredentials((current) => current.map((item) => item.id === updated.id ? updated : item));
      setProviderSecrets((current) => ({ ...current, [provider.id]: "" }));
      setProviderResult(`${provider.label} credential saved locally.`);
    } catch (error) {
      setProviderResult(error instanceof Error ? error.message : String(error));
    }
  };

  const handleDisconnectProvider = async (provider: ProviderCredentialStatus) => {
    try {
      await deleteProviderCredential(provider.id);
      setProviderCredentials((current) => current.map((item) => item.id === provider.id ? { ...item, connected: false } : item));
      setProviderResult(`${provider.label} credential removed locally.`);
    } catch (error) {
      setProviderResult(error instanceof Error ? error.message : String(error));
    }
  };

  return (
    <div className="settings-view">
      <header className="settings-header">
        <button className="btn-ghost" onClick={onBack} type="button">
          ← Back
        </button>
        <h2>Settings</h2>
      </header>

      <div className="settings-body">
        <section className="settings-section">
          <h3>LM Studio</h3>
          <p className="settings-hint">Configure the local inference endpoint.</p>
          <div className="settings-field-row">
            <label>
              Host
              <input
                className="settings-input"
                value={lmHost}
                onChange={(e) => setLmHost(e.target.value)}
              />
            </label>
            <label>
              Port
              <input
                className="settings-input settings-input-sm"
                value={lmPort}
                onChange={(e) => setLmPort(e.target.value)}
              />
            </label>
          </div>
          <div className="settings-actions">
            <button
              className="btn-secondary"
              onClick={handleSaveLmStudio}
              disabled={isSaving}
              type="button"
            >
              Save
            </button>
            <button
              className="btn-secondary"
              onClick={handleTestConnection}
              disabled={isTesting}
              type="button"
            >
              {isTesting ? "Testing…" : "Test connection"}
            </button>
          </div>
          {testResult && <p className="settings-result">{testResult}</p>}
        </section>

        <section className="settings-section">
          <h3>ChatGPT</h3>
          <p className="settings-hint">
            Connect a ChatGPT account to authorize eligible plan-backed requests.
            Dirigent keeps credentials in protected local backend storage; they are
            never sent to the frontend.
          </p>
          <div className="settings-actions">
            <button
              className="btn-secondary"
              onClick={handleConnectChatGPT}
              disabled={isConnectingChatGPT || chatgptAuth?.status === "pending"}
              type="button"
            >
              {chatgptAuth?.status === "pending"
                ? "Waiting for browser approval…"
                : isConnectingChatGPT
                  ? "Opening browser…"
                  : "Continue with ChatGPT"}
            </button>
          </div>
          {chatgptAuth?.status === "connected" && (
            <p className="settings-result">
              Connected: {chatgptAuth.connected.map((account) => account.email || "ChatGPT account").join(", ")}
            </p>
          )}
          {chatgptAuth?.status === "failed" && (
            <p className="settings-result">{chatgptAuth.message}</p>
          )}
        </section>

        <section className="settings-section">
          <h3>Other provider connections</h3>
          <p className="settings-hint">
            These providers currently expose API-key or personal-token integration,
            not a transferable browser-account sign-in for Dirigent.
          </p>
          {providerCredentials.map((provider) => (
            <div className="confirm-detail" key={provider.id}>
              <div className="confirm-value">
                <strong>{provider.label}</strong>
                <p className="settings-hint">{provider.hint}</p>
                <input
                  className="settings-input"
                  type="password"
                  autoComplete="off"
                  placeholder={provider.connected ? "Replace stored credential" : provider.credential_label}
                  value={providerSecrets[provider.id] ?? ""}
                  onChange={(event) => setProviderSecrets((current) => ({ ...current, [provider.id]: event.target.value }))}
                />
                <div className="settings-actions">
                  <button className="btn-secondary" onClick={() => handleSaveProvider(provider)} type="button">
                    {provider.connected ? "Replace" : "Save credential"}
                  </button>
                  {provider.connected && (
                    <button className="btn-secondary" onClick={() => handleDisconnectProvider(provider)} type="button">
                      Disconnect
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {providerResult && <p className="settings-result">{providerResult}</p>}
        </section>

        <section className="settings-section">
          <h3>Application</h3>
          <label className="settings-field">
            Theme
            <select
              className="settings-input"
              value={preferences.theme}
              onChange={(e) =>
                onPreferencesChange({
                  ...preferences,
                  theme: e.target.value as UserPreferences["theme"],
                })
              }
              disabled
            >
              <option value="dark">Dark (default)</option>
              <option value="light">Light (coming soon)</option>
              <option value="system">System (coming soon)</option>
            </select>
          </label>
          <label className="settings-checkbox">
            <input
              type="checkbox"
              checked={preferences.confirmWrites}
              onChange={(e) =>
                onPreferencesChange({
                  ...preferences,
                  confirmWrites: e.target.checked,
                })
              }
              disabled
            />
            Require confirmation for file writes (policy-controlled)
          </label>
          <label className="settings-checkbox">
            <input
              type="checkbox"
              checked={preferences.confirmGit}
              onChange={(e) =>
                onPreferencesChange({
                  ...preferences,
                  confirmGit: e.target.checked,
                })
              }
              disabled
            />
            Require confirmation for git operations (policy-controlled)
          </label>

          <h4 className="settings-subheading">Backend diagnostics</h4>
          <pre className="settings-diagnostics">{backendDiagnostics}</pre>
        </section>

        <section className="settings-section">
          <h3>Workspace</h3>
          <div className="settings-field">
            <span className="settings-label">Current repository</span>
            <code className="settings-repo-path">
              {status.repoPath || "No repository selected"}
            </code>
          </div>
          <div className="settings-actions">
            <button className="btn-primary" onClick={onOpenRepository} type="button">
              Change repository
            </button>
          </div>

          {recentRepos.length > 0 && (
            <div className="settings-recent">
              <span className="settings-label">Recent repositories</span>
              <ul className="settings-recent-list">
                {recentRepos.map((repo) => (
                  <li key={repo}>
                    <button
                      className="btn-ghost settings-recent-item"
                      onClick={() => onSelectRecentRepo(repo)}
                      type="button"
                      title={repo}
                    >
                      {repo}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
