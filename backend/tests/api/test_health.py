"""Health endpoint tests."""

from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from app.core.config import Settings
from app.db.database import Database
from app.main import create_app
from httpx import ASGITransport, AsyncClient


@pytest.mark.anyio
async def test_health_returns_database_status(test_settings: Settings) -> None:
    """The health endpoint reports a real successful SQLite check."""
    app = create_app(test_settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.get("/health", headers={"X-Request-ID": "client-spoofed"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "agentflow-api",
        "version": "0.1.0",
        "database": "ok",
    }
    request_id = response.headers["X-Request-ID"]
    assert request_id != "client-spoofed"
    assert str(UUID(request_id)) == request_id


@pytest.mark.anyio
async def test_cors_allows_configured_frontend_origin(test_settings: Settings) -> None:
    """CORS preflight succeeds only for the configured local frontend."""
    app = create_app(test_settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.anyio
async def test_cors_rejects_unconfigured_origin(test_settings: Settings) -> None:
    """CORS preflight does not grant access to an origin outside configuration."""
    app = create_app(test_settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://unconfigured.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.anyio
async def test_health_returns_safe_error_when_database_is_unavailable(
    tmp_path: Path,
) -> None:
    """A database connection failure must not expose the configured path."""
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        database_path=tmp_path,
        cors_origins=["http://localhost:5173"],
    )

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.get("/health")

    body = response.json()
    assert response.status_code == 503
    assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert body["error"]["retryable"] is True
    assert str(tmp_path) not in response.text
    assert "traceback" not in response.text.lower()


@pytest.mark.anyio
async def test_lifespan_disposes_database_after_exception(test_settings: Settings) -> None:
    """Exceptional shutdown still releases the application-owned engine pool."""
    app = create_app(test_settings)
    database = cast(Database, app.state.database)
    initial_pool = database.engine.pool

    with pytest.raises(RuntimeError, match="forced lifespan failure"):
        async with app.router.lifespan_context(app):
            assert test_settings.resolved_data_dir.is_dir()
            assert test_settings.resolved_database_path.parent.is_dir()
            assert database.is_healthy()
            raise RuntimeError("forced lifespan failure")

    assert database.engine.pool is not initial_pool
