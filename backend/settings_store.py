"""
Persistent settings storage for Dirigent backend.
"""
import json
from typing import Any, Dict, Optional

from backend.paths import get_settings_path

DEFAULTS: Dict[str, Any] = {
    "repo_path": "",
    "lmstudio_host": "127.0.0.1",
    "lmstudio_port": 1234,
    "api_host": "127.0.0.1",
    "api_port": 8000,
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


settings_store = SettingsStore()
