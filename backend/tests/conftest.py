"""Shared backend test fixtures."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Create isolated settings without reading a developer .env file."""
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "test.db",
        cors_origins=["http://localhost:5173"],
    )
    return settings


@pytest.fixture
def anyio_backend() -> str:
    """Run async API tests on the standard-library asyncio backend."""
    return "asyncio"


@pytest.fixture
def migrated_settings(test_settings: Settings) -> Settings:
    """Upgrade an isolated Phase 2 database through the real Alembic path."""
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.attributes["database_path"] = test_settings.resolved_database_path
    command.upgrade(config, "head")
    return test_settings
