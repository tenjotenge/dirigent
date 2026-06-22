import { useState } from "react";
import type { BackendStatus } from "../types";
import {
  testLmStudioConnection,
  updateSettings,
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
