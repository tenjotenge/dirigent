"""
Centralized configuration paths for Dirigent.

Separates development and production data locations.
"""
import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """Return the platform-specific Dirigent application data directory."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        path = Path(base) / "Dirigent"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Dirigent"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        path = Path(xdg) / "dirigent"

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_settings_path() -> Path:
    return get_app_data_dir() / "settings.json"


def get_project_root() -> Path:
    """Resolve the Dirigent project root (repo containing backend/)."""
    env_root = os.environ.get("DIRIGENT_ROOT")
    if env_root:
        return Path(env_root).resolve()

    # backend/paths.py -> project root is two levels up
    return Path(__file__).resolve().parent.parent


def is_development() -> bool:
    return os.environ.get("DIRIGENT_DEV", "").lower() in ("1", "true", "yes")
