interface WelcomeScreenProps {
  onOpenRepository: () => void;
  isOpening: boolean;
  recentRepos?: string[];
  onSelectRecentRepo?: (path: string) => void;
}

export function WelcomeScreen({ 
  onOpenRepository, 
  isOpening,
  recentRepos = [],
  onSelectRecentRepo
}: WelcomeScreenProps) {
  return (
    <div className="welcome-screen">
      <div className="welcome-content">
        <h2>Welcome to Dirigent</h2>
        <p className="welcome-lead">
          Dirigent is a local-first workspace controller for software development.
          It separates AI intelligence from deterministic actions — every tool call
          is logged, policy-checked, and confirmed when needed.
        </p>

        <div className="welcome-steps">
          <div className="welcome-step">
            <span className="welcome-step-num">1</span>
            <div>
              <strong>Open a repository</strong>
              <p>Point Dirigent at a project folder on your machine.</p>
            </div>
          </div>
          <div className="welcome-step">
            <span className="welcome-step-num">2</span>
            <div>
              <strong>Select a model</strong>
              <p>Connect to LM Studio and choose a loaded model.</p>
            </div>
          </div>
          <div className="welcome-step">
            <span className="welcome-step-num">3</span>
            <div>
              <strong>Start working</strong>
              <p>Use natural language to read files, check git status, and more.</p>
            </div>
          </div>
        </div>

        {recentRepos.length > 0 && (
          <div className="welcome-recent">
            <span className="welcome-label">Recent repositories</span>
            <div className="welcome-recent-list">
              {recentRepos.slice(0, 5).map((repo) => (
                <button
                  key={repo}
                  className="btn-ghost welcome-recent-item"
                  onClick={() => onSelectRecentRepo?.(repo)}
                  disabled={isOpening}
                  type="button"
                  title={repo}
                >
                  {repo}
                </button>
              ))}
            </div>
          </div>
        )}

        <button
          className="btn-primary btn-lg"
          onClick={onOpenRepository}
          disabled={isOpening}
          type="button"
        >
          {isOpening ? "Opening…" : "Open Repository"}
        </button>
      </div>
    </div>
  );
}
