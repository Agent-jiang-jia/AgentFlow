"""Centralized application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Configuration loaded from environment variables and backend/.env."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="AGENTFLOW_",
        extra="ignore",
    )

    app_name: str = "AgentFlow API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    data_dir: Path = Path("data")
    database_path: Path = Path("data/agentflow.db")

    model_api_base: str = ""
    model_api_key: SecretStr | None = None
    model_name: str = ""
    model_timeout_seconds: float = Field(default=60.0, gt=0)
    search_provider: Literal["tavily"] = "tavily"
    search_api_base: str = "https://api.tavily.com/search"
    search_api_key: SecretStr | None = None
    search_timeout_seconds: float = Field(default=10.0, gt=0)

    max_upload_size_mb: int = Field(default=20, ge=1)
    max_parsed_chars: int = Field(default=200_000, ge=1_000, le=2_000_000)
    max_artifact_size_mb: int = Field(default=5, ge=1)
    max_agent_loops: int = Field(default=10, ge=1)
    tool_timeout_seconds: float = Field(default=30.0, gt=0)
    web_fetch_timeout_seconds: float = Field(default=10.0, gt=0)
    web_fetch_max_bytes: int = Field(default=2_000_000, ge=1024, le=10_000_000)

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        """Normalize and validate configured CORS origins."""
        normalized = [origin.strip().rstrip("/") for origin in origins if origin.strip()]
        if not normalized:
            raise ValueError("At least one CORS origin must be configured")
        if "*" in normalized:
            raise ValueError("Wildcard CORS origins are not allowed")
        return normalized

    def resolve_path(self, value: Path) -> Path:
        """Resolve a configured path relative to the backend directory."""
        return value.resolve() if value.is_absolute() else (BACKEND_ROOT / value).resolve()

    @property
    def resolved_data_dir(self) -> Path:
        """Return the absolute data root."""
        return self.resolve_path(self.data_dir)

    @property
    def resolved_database_path(self) -> Path:
        """Return the absolute SQLite database file path."""
        return self.resolve_path(self.database_path)

    def ensure_directories(self) -> None:
        """Create runtime data directories if they do not exist."""
        self.resolved_data_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable configuration instance."""
    return Settings()
