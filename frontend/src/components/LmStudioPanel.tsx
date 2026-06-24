import { useState } from "react";
import type { SettingsResponse } from "../api/client";

interface LmStudioPanelProps {
  settings: SettingsResponse | null;
  providerAvailable: boolean;
  onRefreshModels: () => void;
  onTestConnection: () => void;
  onClose: () => void;
}

export function LmStudioPanel({
  settings,
  providerAvailable,
  onRefreshModels,
  onTestConnection,
  onClose,
}: LmStudioPanelProps) {
  const [isLaunching, setIsLaunching] = useState(false);
  const [launchResult, setLaunchResult] = useState<string | null>(null);

  const handleLaunchLmStudio = async () => {
    setIsLaunching(true);
    setLaunchResult(null);
    try {
      // Call Tauri command to launch LM Studio
      const result = await (window as any).__TAURI__.invoke("launch_lm_studio");
      setLaunchResult(result || "LM Studio launch initiated");
    } catch (error) {
      setLaunchResult(error instanceof Error ? error.message : String(error));
    } finally {
      setIsLaunching(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>LM Studio Control Panel</h3>
        </div>
        <div className="modal-body">
          <div className="confirm-detail">
            <span className="confirm-label">Connection Status</span>
            <div className="confirm-value">
              {providerAvailable ? (
                <span className="status-pill online">Connected</span>
              ) : (
                <span className="status-pill offline">Not Connected</span>
              )}
            </div>
          </div>

          <div className="confirm-detail">
            <span className="confirm-label">Endpoint</span>
            <div className="confirm-value">
              <code>{settings?.lmstudio_url || "Not configured"}</code>
            </div>
          </div>

          <div className="confirm-detail">
            <span className="confirm-label">Host</span>
            <div className="confirm-value">{settings?.lmstudio_host || "-"}</div>
          </div>

          <div className="confirm-detail">
            <span className="confirm-label">Port</span>
            <div className="confirm-value">{settings?.lmstudio_port || "-"}</div>
          </div>

          <div className="settings-actions">
            <button
              className="btn-secondary"
              onClick={handleLaunchLmStudio}
              disabled={isLaunching}
              type="button"
            >
              {isLaunching ? "Launching…" : "Launch LM Studio App"}
            </button>
            <button
              className="btn-secondary"
              onClick={onTestConnection}
              type="button"
            >
              Test Connection
            </button>
            <button
              className="btn-secondary"
              onClick={onRefreshModels}
              type="button"
            >
              Refresh Models
            </button>
          </div>

          {launchResult && (
            <div className="confirm-detail">
              <span className="confirm-label">Launch Result</span>
              <div className="confirm-value">{launchResult}</div>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose} type="button">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
