import type { StartupPhase } from "../types";

interface StartupSplashProps {
  phase: StartupPhase;
  message: string;
  error?: string;
}

const PHASE_LABELS: Record<StartupPhase, string> = {
  initializing: "Initializing…",
  starting_backend: "Starting backend…",
  checking_health: "Checking backend health…",
  loading_models: "Loading models…",
  restoring_workspace: "Restoring workspace…",
  ready: "Ready",
  error: "Startup failed",
};

export function StartupSplash({ phase, message, error }: StartupSplashProps) {
  return (
    <div className="startup-splash">
      <div className="startup-content">
        <h1 className="startup-title">Dirigent</h1>
        <p className="startup-tagline">Local-first workspace controller</p>

        <div className="startup-progress">
          <div className="startup-spinner" />
          <div className="startup-phase">{PHASE_LABELS[phase]}</div>
          <div className="startup-message">{message}</div>
        </div>

        {error && (
          <div className="startup-error">
            <strong>Could not start</strong>
            <p>{error}</p>
            <p className="startup-error-hint">
              Ensure Python 3.12+ is installed and backend dependencies are available.
              You can also start the backend manually with{" "}
              <code>python run_backend.py</code>.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
