"""
Configuration for Dirigent backend.
"""
import os

from pydantic_settings import BaseSettings

from backend.settings_store import settings_store


class Settings(BaseSettings):
    """Application settings with env overrides and persisted values."""

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    lmstudio_host: str = "127.0.0.1"
    lmstudio_port: int = 1234
    repo_path: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sync_from_store()

    def _sync_from_store(self) -> None:
        """Load persisted settings; env vars take precedence when set."""
        if not os.environ.get("API_HOST"):
            self.api_host = settings_store.get("api_host", self.api_host)
        if not os.environ.get("API_PORT"):
            self.api_port = settings_store.get("api_port", self.api_port)
        if not os.environ.get("LMSTUDIO_HOST"):
            self.lmstudio_host = settings_store.get("lmstudio_host", self.lmstudio_host)
        if not os.environ.get("LMSTUDIO_PORT"):
            self.lmstudio_port = settings_store.get("lmstudio_port", self.lmstudio_port)
        if not os.environ.get("REPO_PATH"):
            self.repo_path = settings_store.get("repo_path", self.repo_path) or ""

    def persist(self) -> None:
        """Write current values to the settings store."""
        settings_store.update(
            {
                "api_host": self.api_host,
                "api_port": self.api_port,
                "lmstudio_host": self.lmstudio_host,
                "lmstudio_port": self.lmstudio_port,
                "repo_path": self.repo_path,
            }
        )

    @property
    def lmstudio_url(self) -> str:
        return f"http://{self.lmstudio_host}:{self.lmstudio_port}"

    @property
    def api_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"


settings = Settings()
