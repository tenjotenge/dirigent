"""
Persistent settings storage for Dirigent backend.
"""
import json
from typing import Any, Dict, Optional, List
from datetime import datetime

from backend.paths import get_settings_path

DEFAULTS: Dict[str, Any] = {
    "repo_path": "",
    "lmstudio_host": "127.0.0.1",
    "lmstudio_port": 1234,
    "api_host": "127.0.0.1",
    "api_port": 8000,
    "recent_repos": [],
}


class SettingsStore:
    """JSON-backed settings persisted in the app data directory."""

    def __init__(self) -> None:
        self._path = get_settings_path()
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    stored = json.load(f)
                if isinstance(stored, dict):
                    self._data = {**DEFAULTS, **stored}
                    return
            except (json.JSONDecodeError, OSError):
                pass
        self._data = dict(DEFAULTS)
        self.save()

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        self._data.update(updates)
        self.save()
        return self.all()

    def all(self) -> Dict[str, Any]:
        return dict(self._data)

    def add_recent_repo(self, repo_path: str) -> None:
        """Add a repository to recent repositories list."""
        recent: List[Dict[str, str]] = self.get("recent_repos", [])
        
        # Remove if already exists (to move to top)
        recent = [r for r in recent if r.get("path") != repo_path]
        
        # Add to front with timestamp
        recent.insert(0, {
            "path": repo_path,
            "last_used": datetime.now().isoformat(),
        })
        
        # Keep only last 10
        recent = recent[:10]
        
        self.set("recent_repos", recent)

    def get_recent_repos(self) -> List[str]:
        """Get list of recent repository paths."""
        recent: List[Dict[str, str]] = self.get("recent_repos", [])
        return [r["path"] for r in recent if "path" in r]


settings_store = SettingsStore()
