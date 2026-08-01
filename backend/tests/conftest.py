"""Shared backend test fixtures."""

from pathlib import Path

import pytest
from app.core.config import Settings


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
