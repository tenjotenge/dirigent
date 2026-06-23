import type { BackendStatus } from "../types";



interface LeftSidebarProps {

  status: BackendStatus;

  models: string[];

  selectedModel: string;

  onModelChange: (model: string) => void;

  onRefreshModels: () => void;

  onRefreshStatus: () => void;

  onGitStatus: () => void;

  onClearConversation: () => void;

  onOpenRepository: () => void;

  onOpenSettings: () => void;

  isBusy: boolean;

  isRefreshingModels: boolean;

  isOpeningRepo: boolean;

}



function repoLabel(path: string): string {

  if (!path) return "No repository";

  const parts = path.replace(/\\/g, "/").split("/");

  return parts[parts.length - 1] || path;

}



export function LeftSidebar({

  status,

  models,

  selectedModel,

  onModelChange,

  onRefreshModels,

  onRefreshStatus,

  onGitStatus,

  onClearConversation,

  onOpenRepository,

  onOpenSettings,

  isBusy,

  isRefreshingModels,

  isOpeningRepo,

}: LeftSidebarProps) {

  return (

    <aside className="left-sidebar">

      <div className="sidebar-section sidebar-brand">

        <h1>Dirigent</h1>

        <p className="sidebar-tagline">Local-first orchestration</p>

      </div>



      <div className="sidebar-section">

        <h3 className="section-title">Repository</h3>

        <div className="info-card">

          <div className="repo-display">

            <span className={`status-dot ${status.repoLoaded ? "online" : "offline"}`} />

            <div className="repo-display-text">

              <strong>{repoLabel(status.repoPath)}</strong>

              {status.repoPath && (

                <code className="repo-path" title={status.repoPath}>

                  {status.repoPath}

                </code>

              )}

            </div>

          </div>

        </div>

        <button

          className="btn-secondary btn-block"

          onClick={onOpenRepository}

          disabled={isOpeningRepo}

          type="button"

        >

          {isOpeningRepo ? "Opening…" : "Open Repository"}

        </button>

      </div>



      <div className="sidebar-section">

        <h3 className="section-title">Connection</h3>

        <div className="status-grid">

          <div className="status-row">

            <span className="status-label">Backend</span>

            <span className={`status-pill ${status.backendOnline ? "online" : "offline"}`}>

              {status.backendOnline ? "Online" : "Offline"}

            </span>

          </div>

          <div className="status-row">

            <span className="status-label">LM Studio</span>

            <span className={`status-pill ${status.providerAvailable ? "online" : "offline"}`}>

              {status.providerAvailable ? "Reachable" : "Unreachable"}

            </span>

          </div>

          <div className="status-row">

            <span className="status-label">Model</span>

            <span className={`status-pill ${selectedModel ? "online" : "offline"}`}>

              {selectedModel ? "Selected" : "None"}

            </span>

          </div>

          <div className="status-row">

            <span className="status-label">Workspace</span>

            <span className={`status-pill ${status.repoLoaded ? "online" : "offline"}`}>

              {status.repoLoaded ? "Loaded" : "Not loaded"}

            </span>

          </div>

        </div>

        {!status.backendOnline && (

          <p className="status-hint error-hint">

            Backend is offline. Restart the app or run <code>python run_backend.py</code>.

          </p>

        )}

        {status.backendOnline && !status.providerAvailable && (

          <p className="status-hint warning-hint">

            LM Studio is unreachable at {status.lmstudioUrl}. Start LM Studio and load a model.

          </p>

        )}

        <button

          className="btn-ghost btn-sm"

          onClick={onRefreshStatus}

          type="button"

        >

          Refresh status

        </button>

      </div>



      <div className="sidebar-section">

        <h3 className="section-title">Model</h3>

        <div className="model-selector-row">

          <select

            className="model-select"

            value={selectedModel}

            onChange={(e) => onModelChange(e.target.value)}

            disabled={models.length === 0 || !status.repoLoaded}

          >

            {models.length === 0 ? (

              <option value="">No models available</option>

            ) : (

              models.map((model) => (

                <option key={model} value={model}>

                  {model}

                </option>

              ))

            )}

          </select>

          <button

            className="btn-icon"

            onClick={onRefreshModels}

            disabled={isRefreshingModels || !status.backendOnline}

            title="Refresh models"

            type="button"

          >

            ↻

          </button>

        </div>

        {selectedModel && (

          <div className="active-model">

            Active: <code>{selectedModel}</code>

          </div>

        )}

      </div>



      <div className="sidebar-section sidebar-footer-section">

        <h3 className="section-title">Quick Actions</h3>

        <div className="quick-actions">

          <button

            className="btn-secondary btn-block"

            onClick={onRefreshModels}

            disabled={isRefreshingModels || !status.backendOnline}

            type="button"

          >

            Refresh models

          </button>

          <button

            className="btn-secondary btn-block"

            onClick={onGitStatus}

            disabled={isBusy || !status.backendOnline || !status.repoLoaded}

            type="button"

          >

            Git status

          </button>

          <button

            className="btn-secondary btn-block"

            onClick={onClearConversation}

            disabled={isBusy}

            type="button"

          >

            Clear conversation

          </button>

          <button

            className="btn-secondary btn-block"

            onClick={onOpenSettings}

            type="button"

          >

            Settings

          </button>

        </div>

      </div>

    </aside>

  );

}

