"""Centralized settings tests."""

from pathlib import Path

from app.core.config import BACKEND_ROOT, Settings


def test_example_environment_contains_prd_configuration() -> None:
    """The committed example can load every configuration required by the PRD."""
    example_path = BACKEND_ROOT / ".env.example"
    contents = example_path.read_text(encoding="utf-8")
    required_variables = {
        "AGENTFLOW_MODEL_API_BASE",
        "AGENTFLOW_MODEL_API_KEY",
        "AGENTFLOW_MODEL_NAME",
        "AGENTFLOW_MODEL_TIMEOUT_SECONDS",
        "AGENTFLOW_SEARCH_API_KEY",
        "AGENTFLOW_DATABASE_PATH",
        "AGENTFLOW_DATA_DIR",
        "AGENTFLOW_MAX_UPLOAD_SIZE_MB",
        "AGENTFLOW_MAX_ARTIFACT_SIZE_MB",
        "AGENTFLOW_MAX_AGENT_LOOPS",
        "AGENTFLOW_TOOL_TIMEOUT_SECONDS",
        "AGENTFLOW_WEB_FETCH_TIMEOUT_SECONDS",
        "AGENTFLOW_CORS_ORIGINS",
        "AGENTFLOW_LOG_LEVEL",
    }

    assert all(f"{variable}=" in contents for variable in required_variables)
    settings = Settings(_env_file=example_path)
    assert settings.resolved_data_dir == (BACKEND_ROOT / "data").resolve()
    assert settings.resolved_database_path == (BACKEND_ROOT / "data/agentflow.db").resolve()


def test_cors_origins_are_trimmed_and_normalized() -> None:
    """Configured origins tolerate surrounding whitespace and trailing slashes."""
    settings = Settings(
        _env_file=None,
        cors_origins=["  http://localhost:5173/  ", "http://127.0.0.1:5173/"],
    )

    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_relative_paths_are_resolved_from_backend_root() -> None:
    """Runtime paths do not depend on the process working directory."""
    relative_data_dir = Path("runtime") / "data"
    relative_database_path = relative_data_dir / "agentflow.db"
    settings = Settings(
        _env_file=None,
        data_dir=relative_data_dir,
        database_path=relative_database_path,
    )

    assert settings.resolved_data_dir == (BACKEND_ROOT / relative_data_dir).resolve()
    assert settings.resolved_database_path == (BACKEND_ROOT / relative_database_path).resolve()
